"""AmiClient against a fake FreePBX manager on loopback."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from aionecpbx import (
    LIVE_ANSWERED,
    LIVE_ENDED,
    LIVE_RINGING,
    AmiAuthError,
    AmiClient,
    LiveCall,
    async_test_login,
    parse_message,
)
import aionecpbx.ami as ami_module

from .fakes import FakeAmi, wait_for


@pytest.fixture(autouse=True)
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ami_module, "_RECONNECT_MIN", 0.05)
    monkeypatch.setattr(ami_module, "_RECONNECT_MAX", 0.1)


@pytest.fixture
async def fake() -> AsyncIterator[FakeAmi]:
    server = FakeAmi()
    await server.start()
    yield server
    await server.stop()


def test_parse_message() -> None:
    assert parse_message("Event: Hangup\nUniqueid: 1\nUniqueid: 2\nnot a pair") == {
        "Event": "Hangup",
        "Uniqueid": "1",
    }


async def test_call_lifecycle_and_dnd(fake: FakeAmi) -> None:
    changes: list[tuple[str, str]] = []
    states: list[bool] = []

    def on_change(call: LiveCall, what: str) -> None:
        changes.append((call.caller_number or "", what))

    client = AmiClient("127.0.0.1", fake.port, "ha", "s3cret", on_change, states.append)
    client.start()
    await wait_for(lambda: client.connected)

    # Not a call coming in: an outgoing leg is ignored.
    await fake.event(Event="Newchannel", Uniqueid="9", ChannelStateDesc="Down")
    await fake.event(
        Event="Newchannel",
        Uniqueid="1",
        Linkedid="1",
        ChannelStateDesc="Ring",
        CallerIDNum="0491570156",
        CallerIDName="<unknown>",
        Exten="s",
    )
    await wait_for(lambda: len(client.ringing) == 1)
    call = client.ringing[0]
    assert call.caller_name is None
    assert call.extension is None
    await fake.event(Event="DialBegin", Uniqueid="1", Linkedid="1", DestCallerIDNum="103")
    await wait_for(lambda: client.calls["1"].extension == "103")
    await fake.event(Event="Newstate", Uniqueid="2", Linkedid="1", ChannelStateDesc="Up")
    await wait_for(lambda: len(client.active) == 1)
    await fake.event(Event="Hangup", Uniqueid="2", Linkedid="1")  # one leg only
    await fake.event(Event="Hangup", Uniqueid="1", Linkedid="1")
    await wait_for(lambda: not client.calls)
    assert changes == [
        ("0491570156", LIVE_RINGING),
        ("0491570156", LIVE_RINGING),
        ("0491570156", LIVE_ANSWERED),
        ("0491570156", LIVE_ENDED),
    ]

    # Answered through DialEnd instead.
    await fake.event(Event="Newstate", Uniqueid="5", ChannelStateDesc="Ringing")
    await fake.event(Event="DialEnd", Uniqueid="5", DialStatus="ANSWER", DestCallerIDNum="104")
    await wait_for(lambda: len(client.active) == 1)
    assert client.active[0].extension == "104"

    assert await client.get_dnd("103") is False
    await client.set_dnd("103", True)
    assert fake.db == {"DND/103": "YES"}
    assert await client.get_dnd("103") is True
    await client.set_dnd("103", False)
    assert fake.db == {}

    # A dropped connection ends every live call and reconnects by itself.
    await fake.drop()
    await wait_for(lambda: not client.connected)
    assert changes[-1][1] == LIVE_ENDED
    await wait_for(lambda: client.connected)
    assert states[:3] == [True, False, True]
    await client.stop()
    with pytest.raises(ConnectionError):
        await client.action("Ping")


async def test_wrong_secret_stops_trying(fake: FakeAmi) -> None:
    client = AmiClient("127.0.0.1", fake.port, "ha", "wrong", lambda _c, _w: None)
    client.start()
    await wait_for(lambda: client.last_error is not None)
    assert client.last_error.startswith("login:")
    await wait_for(lambda: client._task is not None and client._task.done())
    await client.stop()


async def test_bad_event_is_logged_not_fatal(
    fake: FakeAmi, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = AmiClient("127.0.0.1", fake.port, "ha", "s3cret", lambda _c, _w: None)

    def boom(_event: str, _msg: dict[str, str]) -> None:
        raise ValueError("odd")

    monkeypatch.setattr(client, "_call_event", boom)
    client.start()
    await wait_for(lambda: client.connected)
    await fake.event(Event="Newchannel", Uniqueid="1")
    await fake.event(Event="Unrelated")  # no id: ignored before _call_event
    assert client.connected
    await client.stop()


async def test_test_login(fake: FakeAmi) -> None:
    await async_test_login("127.0.0.1", fake.port, "ha", "s3cret")
    with pytest.raises(AmiAuthError):
        await async_test_login("127.0.0.1", fake.port, "ha", "nope")
    with pytest.raises(OSError):
        await async_test_login("127.0.0.1", 1, "ha", "s3cret")
