"""Fake phone system (SMDR) and fake FreePBX manager (AMI) on loopback."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib

from aionecpbx import parse_message


async def wait_for(predicate: Callable[[], bool], timeout: float = 3.0) -> None:
    """Wait until ``predicate()`` is true."""
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.02)


class FakePbx:
    """A TCP server that behaves like the SL2100 SMDR port."""

    def __init__(self) -> None:
        self.writers: list[asyncio.StreamWriter] = []
        self.connected = asyncio.Event()
        self.server: asyncio.Server | None = None
        self.port = 0

    async def start(self) -> None:
        await self.start_on(0)

    async def start_on(self, port: int) -> None:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", port)
        self.port = self.server.sockets[0].getsockname()[1]

    async def _handle(self, _reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.writers.append(writer)
        self.connected.set()

    async def send(self, text: str) -> None:
        for writer in self.writers:
            writer.write(text.encode("ascii"))
            await writer.drain()

    async def drop_clients(self) -> None:
        for writer in self.writers:
            writer.close()
        self.writers.clear()
        self.connected.clear()

    async def stop(self) -> None:
        await self.drop_clients()
        if self.server:
            self.server.close()
            # wait_closed() also waits for open client connections.
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.server.wait_closed(), 1)


class FakeAmi:
    """Enough of Asterisk's manager to log in, send call events and keep DND."""

    def __init__(self, secret: str = "s3cret") -> None:
        self.secret = secret
        self.writers: list[asyncio.StreamWriter] = []
        self.logged_in = asyncio.Event()
        self.db: dict[str, str] = {}
        self.server: asyncio.Server | None = None
        self.port = 0

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"Asterisk Call Manager/9.0.0\r\n")
        await writer.drain()
        buffer: list[str] = []
        try:
            while raw := await reader.readline():
                line = raw.decode().rstrip("\r\n")
                if line:
                    buffer.append(line)
                    continue
                if buffer:
                    await self._action(parse_message("\n".join(buffer)), writer)
                    buffer = []
        except (ConnectionError, asyncio.CancelledError):
            pass

    async def _action(self, msg: dict[str, str], writer: asyncio.StreamWriter) -> None:
        aid = msg.get("ActionID", "")
        action = msg.get("Action", "").lower()
        if action == "login":
            ok = msg.get("Secret") == self.secret
            reply = "Success" if ok else "Error"
            text = "Authentication accepted" if ok else "Authentication failed"
            writer.write(
                f"Response: {reply}\r\nActionID: {aid}\r\nMessage: {text}\r\n\r\n".encode()
            )
            if ok:
                self.writers.append(writer)
                self.logged_in.set()
        elif action == "dbput":
            self.db[f"{msg['Family']}/{msg['Key']}"] = msg["Val"]
            writer.write(
                f"Response: Success\r\nActionID: {aid}\r\nMessage: Updated database successfully\r\n\r\n".encode()
            )
        elif action == "dbdel":
            self.db.pop(f"{msg['Family']}/{msg['Key']}", None)
            writer.write(
                f"Response: Success\r\nActionID: {aid}\r\nMessage: Key deleted successfully\r\n\r\n".encode()
            )
        elif action == "dbget":
            key = f"{msg['Family']}/{msg['Key']}"
            if key in self.db:
                writer.write(
                    f"Response: Success\r\nActionID: {aid}\r\nEventList: start\r\nMessage: Result will follow\r\n\r\n".encode()
                )
                writer.write(
                    f"Event: DBGetResponse\r\nFamily: {msg['Family']}\r\nKey: {msg['Key']}\r\nVal: {self.db[key]}\r\nActionID: {aid}\r\n\r\n".encode()
                )
            else:
                writer.write(
                    f"Response: Error\r\nActionID: {aid}\r\nMessage: Database entry not found\r\n\r\n".encode()
                )
        else:
            writer.write(f"Response: Success\r\nActionID: {aid}\r\n\r\n".encode())
        await writer.drain()

    async def event(self, **fields: str) -> None:
        text = "".join(f"{k}: {v}\r\n" for k, v in fields.items()) + "\r\n"
        for writer in self.writers:
            writer.write(text.encode())
            await writer.drain()

    async def drop(self) -> None:
        """Close every client connection, as a FreePBX restart would."""
        for writer in self.writers:
            writer.close()
        self.writers.clear()

    async def stop(self) -> None:
        await self.drop()
        if self.server:
            self.server.close()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.server.wait_closed(), 1)
