"""The subset of ``pymodbus.client.ModbusTcpClient`` that ``e2e/`` uses, over fakeplc's protocol."""

from __future__ import annotations

import socket
import struct


class _Response:
    def __init__(self, registers: list[int]) -> None:
        self.registers = registers


class ModbusTcpClient:
    def __init__(self, host: str, port: int = 502, **_: object) -> None:
        self.address = (host, port)
        self.sock: socket.socket | None = None

    def connect(self) -> bool:
        self.sock = socket.create_connection(self.address)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return True

    def _receive(self, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise ConnectionError("fakeplc closed the connection")
            data += chunk
        return data

    def read_holding_registers(self, address: int, count: int = 1, device_id: int = 1, **_: object) -> _Response:
        self.sock.sendall(b"R" + struct.pack("<HH", address, count))
        return _Response(list(struct.unpack(f"<{count}H", self._receive(2 * count))))

    def write_registers(self, address: int, values: list[int], device_id: int = 1, **_: object) -> None:
        payload = struct.pack(f"<{len(values)}H", *values)
        self.sock.sendall(b"W" + struct.pack("<HH", address, len(values)) + payload)
        self._receive(1)

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None
