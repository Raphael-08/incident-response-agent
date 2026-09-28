from agent.log_normalizer import normalize_log


def test_strips_timestamp_ip_and_pod_hash():
    log = (
        "2026-06-28T17:21:09Z ERROR orders-api-5c7b9d8f6-x2k9p connect to 10.0.4.12:5432 failed "
        "in pod search-service-7d9f8"
    )
    assert normalize_log(log) == (
        "<TIME> ERROR orders-api-<POD> connect to <IP> failed in pod search-service-<POD>"
    )


def test_strips_uuid_hex_and_long_numbers():
    log = "request 3f2b8c1e-9a4d-4e2b-8f1a-2c3d4e5f6a7b addr 0x7ffe12 exp=1783170700"
    assert normalize_log(log) == "request <UUID> addr <HEX> exp=<NUM>"


def test_keeps_meaningful_error_text():
    log = "FATAL: remaining connection slots are reserved, pool_size=10 v2.3.1 redis-cart:6379"
    assert normalize_log(log) == log


def test_same_error_from_different_runs_normalizes_equal():
    a = "2026-06-03T14:08:11Z payment-api-6f7d8c9b5-abcde 10.0.1.5 too many clients"
    b = "2026-07-09T02:04:19Z payment-api-7a8b9c0d1-zyxwv 10.0.9.9 too many clients"
    assert normalize_log(a) == normalize_log(b)
