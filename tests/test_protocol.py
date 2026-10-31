from __future__ import annotations

import pytest

from pyffb.protocol import (
    ProtocolError,
    ReplyKind,
    format_execute,
    format_get,
    format_set,
    parse_line,
    pct_to_15bit,
    pct_to_u8,
    raw_to_pct,
    u8_to_pct,
    value_15bit_to_pct,
)


def test_parse_get():
    reply = parse_line("[axis.0.power?|22937]\r\n")
    assert reply is not None
    assert reply.kind is ReplyKind.GET
    assert reply.path == "axis.0.power"
    assert reply.value == "22937"
    assert reply.as_int() == 22937


def test_parse_set_ok():
    reply = parse_line("[axis.0.power=20000|OK]")
    assert reply is not None
    assert reply.kind is ReplyKind.SET
    assert reply.path == "axis.0.power"
    assert reply.sent_value == "20000"
    assert reply.status == "OK"
    assert reply.ok


def test_parse_set_error():
    reply = parse_line("[axis.0.power=20000|ERR]")
    assert reply is not None
    assert reply.kind is ReplyKind.SET
    assert not reply.ok


def test_parse_execute():
    reply = parse_line("[sys.save|OK]")
    assert reply is not None
    assert reply.kind is ReplyKind.EXECUTE
    assert reply.path == "sys.save"
    assert reply.status == "OK"


def test_parse_hex_and_bool():
    assert parse_line("[x.cmd?|x4d2]").as_int() == 1234
    assert parse_line("[main.0.ffbactive?|1]").as_bool() is True
    assert parse_line("[main.0.ffbactive?|0]").as_bool() is False


def test_parse_noise():
    assert parse_line("") is None
    noise = parse_line("BOOT OK")
    assert noise is not None
    assert noise.kind is ReplyKind.UNKNOWN


def test_formatting():
    assert format_get("axis.0.power") == "axis.0.power?\r\n"
    assert format_set("axis.0.power", 100) == "axis.0.power=100\r\n"
    assert format_execute("sys.save") == "sys.save\r\n"
    with pytest.raises(ProtocolError):
        format_get("axis.0.power\nbad")
    with pytest.raises(ProtocolError):
        format_set("axis.0.power", "10|OK")


def test_scaling():
    assert pct_to_15bit(0) == 0
    assert pct_to_15bit(100) == 32767
    assert pct_to_15bit(50) == 16384
    assert value_15bit_to_pct(32767) == 100
    assert value_15bit_to_pct(0) == 0
    assert pct_to_u8(25) == 64
    assert u8_to_pct(254) == 100
    assert raw_to_pct(500, 1000) == 50
    assert pct_to_u8(150) == 255
