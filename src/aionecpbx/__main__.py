"""Command-line tool: ``python -m aionecpbx`` or ``aionecpbx``.

Examples::

    aionecpbx parse "IC 0001 10:00 001 00:01:00 103 0491570156"
    aionecpbx listen 192.168.0.10
    aionecpbx ami 192.168.0.20 --username homeassistant --secret ...
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
import contextlib
from datetime import datetime
import json
import logging
import sys
from typing import Any

from . import (
    DEFAULT_AMI_PORT,
    DEFAULT_SMDR_PORT,
    AmiAuthError,
    AmiClient,
    LiveCall,
    SmdrClient,
    is_record_line,
    parse_line,
)


def _print(value: Any) -> None:
    print(json.dumps(value, default=str), flush=True)


def _record(line: str) -> dict[str, Any] | None:
    if not is_record_line(line):
        return None
    record = parse_line(line, now=datetime.now())
    return record.as_dict() if record else None


async def _listen(host: str, port: int) -> None:
    def on_line(line: str) -> None:
        _print(_record(line) or {"raw": line, "record": False})

    def on_state(connected: bool) -> None:
        print(f"# {'connected to' if connected else 'lost'} {host}:{port}", file=sys.stderr)

    client = SmdrClient(host, port, on_line, on_state)
    client.start()
    try:
        await asyncio.Event().wait()
    finally:
        await client.stop()


async def _ami(host: str, port: int, username: str, secret: str) -> None:
    def on_change(call: LiveCall, what: str) -> None:
        _print({"change": what, **call.__dict__})

    client = AmiClient(host, port, username, secret, on_change)
    client.start()
    try:
        # The client only gives up when FreePBX rejects the login.
        assert client._task is not None
        await client._task
        raise AmiAuthError(client.last_error or "login rejected")
    finally:
        await client.stop()


def main(argv: Sequence[str] | None = None) -> None:
    """Run the command-line tool."""
    parser = argparse.ArgumentParser(prog="aionecpbx", description=__doc__.splitlines()[0])
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    parse = sub.add_parser("parse", help="parse one SMDR line")
    parse.add_argument("line")

    listen = sub.add_parser("listen", help="print each call as the phone system logs it")
    listen.add_argument("host")
    listen.add_argument("--port", type=int, default=DEFAULT_SMDR_PORT)

    ami = sub.add_parser("ami", help="print live calls from FreePBX")
    ami.add_argument("host")
    ami.add_argument("--port", type=int, default=DEFAULT_AMI_PORT)
    ami.add_argument("--username", required=True)
    ami.add_argument("--secret", required=True)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    if args.command == "parse":
        _print(_record(args.line) or {"raw": args.line, "record": False})
        return
    with contextlib.suppress(KeyboardInterrupt):  # pragma: no cover
        try:
            if args.command == "listen":
                asyncio.run(_listen(args.host, args.port))
            else:
                asyncio.run(_ami(args.host, args.port, args.username, args.secret))
        except AmiAuthError as err:
            print(f"error: {err}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
