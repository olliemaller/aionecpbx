"""The command-line tool."""

from __future__ import annotations

import json

import pytest

from aionecpbx.__main__ import main


def test_parse(capsys: pytest.CaptureFixture[str]) -> None:
    main(["parse", "IC 0001  10:00  001   00:01:00  103   0491570156   0:08"])
    out = json.loads(capsys.readouterr().out)
    assert out["direction"] == "incoming"
    assert out["station"] == "103"
    main(["parse", "CLSS  TIME   LINE   DURATION"])
    assert json.loads(capsys.readouterr().out)["record"] is False


def test_needs_a_command() -> None:
    with pytest.raises(SystemExit):
        main([])


async def test_listen_prints_calls(capsys: pytest.CaptureFixture[str]) -> None:
    import asyncio

    from aionecpbx.__main__ import _listen

    from .fakes import FakePbx, wait_for

    pbx = FakePbx()
    await pbx.start()
    task = asyncio.create_task(_listen("127.0.0.1", pbx.port))
    await pbx.connected.wait()
    await pbx.send("IC 0001  10:00  001   00:01:00  103   0491570156   0:08\nhello\n")
    lines: list[str] = []

    def got_two() -> bool:
        lines.extend(capsys.readouterr().out.splitlines())
        return len(lines) >= 2

    await wait_for(got_two)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await pbx.stop()
    assert json.loads(lines[0])["station"] == "103"
    assert json.loads(lines[1])["record"] is False


async def test_ami_wrong_secret(capsys: pytest.CaptureFixture[str]) -> None:
    from aionecpbx import AmiAuthError
    from aionecpbx.__main__ import _ami

    from .fakes import FakeAmi

    fake = FakeAmi()
    await fake.start()
    with pytest.raises(AmiAuthError):
        await _ami("127.0.0.1", fake.port, "ha", "wrong")
    await fake.stop()


def test_main_reports_login_error(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from aionecpbx import AmiAuthError
    import aionecpbx.__main__ as cli

    async def fail(*_: object) -> None:
        raise AmiAuthError("nope")

    async def quiet(*_: object) -> None:
        return None

    monkeypatch.setattr(cli, "_ami", fail)
    with pytest.raises(SystemExit):
        main(["ami", "127.0.0.1", "--username", "u", "--secret", "s"])
    assert "error: nope" in capsys.readouterr().err
    monkeypatch.setattr(cli, "_listen", quiet)
    main(["-v", "listen", "127.0.0.1"])
