import os
import socket

import pytest

from zonecap.c5.audit import finish_drain, open_queue, start_drain
from zonecap.c5.harness import _order, distribution, merged_configuration, nearest_rank
from zonecap.c5.matrix import rotated
from zonecap.c5.resp import FakeRedisServer, RedisRevocationStore, RespError


def test_nearest_rank_has_no_interpolation():
    ordered = [10, 20, 30, 40]
    assert nearest_rank(ordered, 0.50) == 20
    assert nearest_rank(ordered, 0.75) == 30
    assert nearest_rank(ordered, 0.99) == 40


def test_distribution_reports_mad_and_bounds():
    result = distribution([5, 1, 3, 2, 4])
    assert result["p50_ns"] == 3
    assert result["median_absolute_deviation_ns"] == 1
    assert (result["minimum_ns"], result["maximum_ns"]) == (1, 5)
    assert result["zero_or_negative_samples"] == 0


def test_order_shuffles_units_but_keeps_trace_steps_contiguous():
    steps = [{"unit": 0}, {"unit": 1}, {"unit": 1}, {"unit": 1}, {"unit": 2}, {"unit": 3}]
    order = _order(steps, 104729)
    assert sorted(order) == list(range(6))
    start = order.index(1)
    assert order[start : start + 3] == [1, 2, 3]
    assert _order(steps, 104729) == order


def test_configuration_overrides_merge_nested_settings():
    config = {
        "defaults": {"warmup": 10, "pep": {"verify_signatures": True, "audit_enabled": True}},
        "configurations": [{"name": "unsigned", "pep": {"verify_signatures": False}}],
    }
    merged = merged_configuration(config, "unsigned")
    assert merged["pep"] == {"verify_signatures": False, "audit_enabled": True}
    assert merged["warmup"] == 10


def test_rotation_counterbalances_configuration_order():
    assert rotated(["a", "b", "c"], 0) == ["a", "b", "c"]
    assert rotated(["a", "b", "c"], 4) == ["b", "c", "a"]


def test_audit_drain_counts_every_record(tmp_path):
    read_fd, write_fd, granted = open_queue(1 << 16)
    assert granted >= 1 << 16
    process = start_drain(read_fd, tmp_path / "audit.log", None)
    for index in range(1000):
        os.write(write_fd, b'{"i":%d}\n' % index)
    summary = finish_drain(process, write_fd, tmp_path / "audit.log")
    assert summary["records"] == 1000


def test_redis_revocation_store_pipelines_chain_lookup():
    with FakeRedisServer() as server:
        store = RedisRevocationStore("127.0.0.1", server.port)
        store.load(["revoked:a", "revoked:b"])
        assert store.size() == 2
        assert store.any_revoked(["root", "revoked:b"])
        assert not store.any_revoked(["root", "child"])


def test_redis_revocation_store_reconnects_after_a_failed_lookup():
    with FakeRedisServer() as server:
        store = RedisRevocationStore("127.0.0.1", server.port)
        store.load(["revoked:a"])
        store.connection.sock.shutdown(socket.SHUT_RDWR)
        with pytest.raises((OSError, RespError)):
            store.any_revoked(["revoked:a"])
        assert store.any_revoked(["revoked:a"])
        assert store.reconnects == 1
