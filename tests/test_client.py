"""SmdrClient against a fake phone system on loopback."""

from __future__ import annotations

from collections.abc import AsyncIterator
import logging

import pytest

from aionecpbx import SmdrClient, async_probe
import aionecpbx.client as client_module

from .fakes import FakePbx, wait_for


@pytest.fixture(autouse=True)
def fast_reconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module, "RECONNECT_MIN", 0.05)
    monkeypatch.setattr(client_module, "RECONNECT_MAX", 0.1)


@pytest.fixture
async def pbx() -> AsyncIterator[FakePbx]:
    fake = FakePbx()
    await fake.start()
    yield fake
    await fake.stop()


async def test_reads_lines_and_reconnects(pbx: FakePbx) -> None:
    lines: list[str] = []
    states: list[bool] = []
    client = SmdrClient("127.0.0.1", pbx.port, lines.append, states.append)
    client.start()
    client.start()  # a second start is ignored
    await wait_for(lambda: client.connected)
    await pbx.send("IC 0001 10:00 001 00:01:00 103 0491570156\r\n\r\n\x0cOG 0002")
    await pbx.send(" 10:05 002 00:00:30 104 0491570157\n")
    await wait_for(lambda: len(lines) == 2)
    assert lines[0].startswith("IC 0001")
    assert lines[1].startswith("OG 0002 10:05")
    assert client.lines_received == 2

    await pbx.drop_clients()
    await wait_for(lambda: not client.connected)
    assert client.last_error == "closed by PBX"
    await wait_for(lambda: client.connected)  # back by itself
    assert states == [True, False, True]
    await client.stop()
    assert client.connected is False


async def test_async_callback_and_errors(pbx: FakePbx, caplog: pytest.LogCaptureFixture) -> None:
    """Async callbacks are awaited; a failing callback doesn't drop the link."""
    seen: list[str] = []

    async def on_line(line: str) -> None:
        if "BAD" in line:
            raise ValueError("boom")
        seen.append(line)

    client = SmdrClient("127.0.0.1", pbx.port, on_line)
    client.start()
    await wait_for(lambda: client.connected)
    with caplog.at_level(logging.ERROR):
        await pbx.send("BAD line\nGOOD line\n")
        await wait_for(lambda: seen == ["GOOD line"])
    assert "Error handling SMDR line" in caplog.text
    await client.stop()


async def test_long_line_without_ending(pbx: FakePbx) -> None:
    lines: list[str] = []
    client = SmdrClient("127.0.0.1", pbx.port, lines.append)
    client.start()
    await wait_for(lambda: client.connected)
    await pbx.send("X" * 3000)
    await wait_for(lambda: len(lines) == 1)
    assert len(lines[0]) == 3000
    await client.stop()


async def test_unreachable_keeps_trying() -> None:
    client = SmdrClient("127.0.0.1", 1, lambda _line: None)
    client.start()
    await wait_for(lambda: client.last_error is not None)
    assert client.last_error.startswith("connect:")
    assert not client.connected
    await client.stop()


async def test_probe(pbx: FakePbx) -> None:
    await async_probe("127.0.0.1", pbx.port)
    with pytest.raises(OSError):
        await async_probe("127.0.0.1", 1)
