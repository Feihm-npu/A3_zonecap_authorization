from __future__ import annotations

"""Minimal Redis (RESP2) client for the exp-23 remote-revocation diagnostic.

The PEP sends one pipelined batch of ``SISMEMBER`` commands per decision, one
per chain token, so a lookup costs one round trip on any Redis version.  A
small in-process server implements the same commands for unit tests and
development runs only; confirmatory runs use a real, pinned Redis server.
"""

import socket
import socketserver
import threading
from typing import Any


REVOCATION_KEY = "zonecap:c5:revoked"


def encode_command(*arguments: str | bytes) -> bytes:
    parts = [b"*%d\r\n" % len(arguments)]
    for argument in arguments:
        data = argument.encode("utf-8") if isinstance(argument, str) else argument
        parts.append(b"$%d\r\n%s\r\n" % (len(data), data))
    return b"".join(parts)


class RespError(RuntimeError):
    pass


class RespConnection:
    def __init__(self, host: str, port: int, *, timeout_s: float = 0.25) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout_s)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.reader = self.sock.makefile("rb")

    def close(self) -> None:
        self.reader.close()
        self.sock.close()

    def _reply(self) -> Any:
        line = self.reader.readline()
        if not line.endswith(b"\r\n"):
            raise RespError("connection closed")
        kind, body = line[:1], line[1:-2]
        if kind == b":":
            return int(body)
        if kind == b"+":
            return body.decode("utf-8")
        if kind == b"-":
            raise RespError(body.decode("utf-8"))
        if kind == b"$":
            length = int(body)
            if length < 0:
                return None
            data = self.reader.read(length + 2)
            return data[:-2]
        if kind == b"*":
            return [self._reply() for _ in range(int(body))]
        raise RespError(f"unexpected reply type {kind!r}")

    def command(self, *arguments: str | bytes) -> Any:
        self.sock.sendall(encode_command(*arguments))
        return self._reply()

    def pipeline(self, commands: list[tuple[str, ...]]) -> list[Any]:
        self.sock.sendall(b"".join(encode_command(*command) for command in commands))
        return [self._reply() for _ in commands]


class RedisRevocationStore:
    """Revocation lookup against a Redis set.

    Any error or a reply slower than ``timeout_s`` raises, so the PEP denies
    that request; the connection is then dropped and re-established on the
    next lookup.  Set-up calls use a separate connection with a long timeout.
    """

    epoch = None

    def __init__(
        self, host: str, port: int, *, key: str = REVOCATION_KEY, timeout_s: float = 0.1
    ) -> None:
        self.host = host
        self.port = port
        self.key = key
        self.timeout_s = timeout_s
        self.reconnects = 0
        self.connection: RespConnection | None = RespConnection(host, port, timeout_s=timeout_s)

    def any_revoked(self, token_ids: list[str]) -> bool:
        if self.connection is None:
            self.connection = RespConnection(self.host, self.port, timeout_s=self.timeout_s)
            self.reconnects += 1
        try:
            replies = self.connection.pipeline(
                [("SISMEMBER", self.key, token_id) for token_id in token_ids]
            )
        except Exception:
            try:
                self.connection.close()
            finally:
                self.connection = None
            raise
        return any(replies)

    def _admin(self) -> RespConnection:
        return RespConnection(self.host, self.port, timeout_s=10.0)

    def load(self, token_ids: list[str], *, batch: int = 1000) -> None:
        admin = self._admin()
        try:
            admin.command("DEL", self.key)
            for start in range(0, len(token_ids), batch):
                admin.command("SADD", self.key, *token_ids[start : start + batch])
        finally:
            admin.close()

    def size(self) -> int:
        admin = self._admin()
        try:
            return int(admin.command("SCARD", self.key))
        finally:
            admin.close()


class _FakeRedisHandler(socketserver.StreamRequestHandler):
    def setup(self) -> None:
        super().setup()
        # Like Redis, reply without Nagle delay; otherwise pipelined replies
        # stall on the client's delayed acknowledgement.
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def _read_command(self) -> list[bytes] | None:
        header = self.rfile.readline()
        if not header:
            return None
        if not header.startswith(b"*"):
            raise RespError("inline commands are not supported")
        arguments = []
        for _ in range(int(header[1:-2])):
            length = int(self.rfile.readline()[1:-2])
            arguments.append(self.rfile.read(length + 2)[:-2])
        return arguments

    def handle(self) -> None:
        sets: dict[bytes, set[bytes]] = self.server.sets  # type: ignore[attr-defined]
        lock: threading.Lock = self.server.lock  # type: ignore[attr-defined]
        while True:
            arguments = self._read_command()
            if arguments is None:
                return
            name = arguments[0].upper()
            with lock:
                if name == b"PING":
                    reply = b"+PONG\r\n"
                elif name == b"SADD":
                    members = sets.setdefault(arguments[1], set())
                    before = len(members)
                    members.update(arguments[2:])
                    reply = b":%d\r\n" % (len(members) - before)
                elif name == b"SISMEMBER":
                    reply = b":%d\r\n" % (arguments[2] in sets.get(arguments[1], set()))
                elif name == b"SCARD":
                    reply = b":%d\r\n" % len(sets.get(arguments[1], set()))
                elif name == b"DEL":
                    reply = b":%d\r\n" % sum(sets.pop(key, None) is not None for key in arguments[1:])
                else:
                    reply = b"-ERR unsupported command\r\n"
            self.wfile.write(reply)


class FakeRedisServer(socketserver.ThreadingTCPServer):
    """Development/test stand-in; never used for a confirmatory run."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port: int = 0) -> None:
        super().__init__(("127.0.0.1", port), _FakeRedisHandler)
        self.sets: dict[bytes, set[bytes]] = {}
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)

    def __enter__(self) -> "FakeRedisServer":
        self.thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.shutdown()
        self.server_close()

    @property
    def port(self) -> int:
        return self.server_address[1]


def main() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Development-only fake Redis server.")
    parser.add_argument("--serve-fake", action="store_true", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--cpu-core", type=int)
    arguments = parser.parse_args()
    if arguments.cpu_core is not None:
        os.sched_setaffinity(0, {arguments.cpu_core})
    server = FakeRedisServer(arguments.port)
    print(server.port, flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
