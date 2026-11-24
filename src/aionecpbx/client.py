"""TCP client that reads the SMDR stream from an NEC SL2100 / SV9100."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
import logging
import socket

_LOGGER = logging.getLogger(__name__)

#: SMDR output port on Australian SL2100s (Program 10-20, type 5).
DEFAULT_SMDR_PORT = 4001
#: Seconds between reconnect attempts: doubles from the minimum to the maximum.
RECONNECT_MIN = 5
RECONNECT_MAX = 300
#: A connection counts as healthy, and the back-off starts again from the
#: minimum, once a line arrives or it has stayed up this many seconds.
STABLE_AFTER = 60
CONNECT_TIMEOUT = 10
#: TCP keepalive, so a phone system that vanished is noticed within about
#: 90 seconds (idle, then interval x count).
KEEPALIVE_IDLE = 60
KEEPALIVE_INTERVAL = 10
KEEPALIVE_COUNT = 3

LineCallback = Callable[[str], Awaitable[None] | None]
StateCallback = Callable[[bool], None]


async def async_probe(host: str, port: int, timeout: float = CONNECT_TIMEOUT) -> None:
    """Open and close a connection; raises OSError / TimeoutError on failure."""
    _reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    writer.close()
    with contextlib.suppress(OSError):
        await writer.wait_closed()


def _enable_keepalive(writer: asyncio.StreamWriter) -> None:
    """Turn on TCP keepalive so a PBX that vanished (reboot, cable, switch)
    is noticed and the client reconnects, instead of waiting forever."""
    sock = writer.get_extra_info("socket")
    if sock is None:
        return
    with contextlib.suppress(OSError, AttributeError):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        for name, value in (
            ("TCP_KEEPIDLE", KEEPALIVE_IDLE),
            ("TCP_KEEPINTVL", KEEPALIVE_INTERVAL),
            ("TCP_KEEPCNT", KEEPALIVE_COUNT),
        ):
            if hasattr(socket, name):
                sock.setsockopt(socket.IPPROTO_TCP, getattr(socket, name), value)


def _clean(data: bytes) -> str:
    """Decode bytes, dropping control characters other than tab."""
    text = data.decode("ascii", errors="replace")
    return "".join(ch for ch in text if ch == "\t" or ch >= " ").replace("�", "")


class SmdrClient:
    """Keeps a connection to the PBX's SMDR port open and hands over each line.

    The SL2100 is the TCP server (Program 10-20, external equipment type 5)
    and simply prints a text line when each call ends. If the connection
    drops, the client reconnects with back-off. Only one client can hold the
    SMDR port at a time, so close any other call-logging software.
    """

    def __init__(
        self,
        host: str,
        port: int,
        on_line: LineCallback,
        on_state: StateCallback | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._on_line = on_line
        self._on_state = on_state
        self._task: asyncio.Task[None] | None = None
        self._writer: asyncio.StreamWriter | None = None
        self.connected = False
        self.lines_received = 0
        self.last_error: str | None = None

    def start(self) -> None:
        """Start the background read loop."""
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(
                self._run(), name=f"aionecpbx smdr {self.host}:{self.port}"
            )

    async def stop(self) -> None:
        """Stop the read loop and close the socket."""
        task, self._task = self._task, None
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self._close()
        self._set_connected(False)

    def _set_connected(self, value: bool) -> None:
        if value != self.connected:
            self.connected = value
            if self._on_state:
                self._on_state(value)

    async def _close(self) -> None:
        writer, self._writer = self._writer, None
        if writer:
            writer.close()
            with contextlib.suppress(OSError, asyncio.CancelledError):
                await writer.wait_closed()

    async def _run(self) -> None:
        delay = RECONNECT_MIN
        while True:
            try:
                if await self._connect_once():
                    delay = RECONNECT_MIN
            except Exception as err:  # a failing callback must not end the loop silently
                self.last_error = f"error: {err!r}"
                _LOGGER.exception(
                    "SMDR client for %s:%s failed; reconnecting", self.host, self.port
                )
                await self._close()
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

    async def _connect_once(self) -> bool:
        """Connect and read until the link drops. True if the link was healthy:
        a line arrived or it stayed up for ``STABLE_AFTER`` seconds. A phone
        system that accepts and closes straight away keeps the back-off growing."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), CONNECT_TIMEOUT
            )
            self._writer = writer
        except (OSError, TimeoutError) as err:
            self.last_error = f"connect: {err}"
            _LOGGER.debug("SMDR connect to %s:%s failed: %s", self.host, self.port, err)
            return False
        loop = asyncio.get_running_loop()
        started, lines_before = loop.time(), self.lines_received
        _enable_keepalive(writer)
        _LOGGER.info("Connected to SMDR at %s:%s", self.host, self.port)
        self.last_error = None
        try:
            self._set_connected(True)
            await self._read(reader)
        except (OSError, asyncio.IncompleteReadError) as err:
            self.last_error = f"read: {err}"
            _LOGGER.warning("SMDR connection to %s lost: %s", self.host, err)
        finally:
            await self._close()
            self._set_connected(False)
        return self.lines_received > lines_before or loop.time() - started >= STABLE_AFTER

    async def _read(self, reader: asyncio.StreamReader) -> None:
        buffer = b""
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                self.last_error = "closed by PBX"
                _LOGGER.info("SMDR connection closed by %s", self.host)
                return
            buffer += chunk.replace(b"\r\n", b"\n").replace(b"\r", b"\n").replace(b"\f", b"\n")
            *lines, buffer = buffer.split(b"\n")
            for raw in lines:
                await self._deliver(raw)
            if len(buffer) > 2048:  # no line ending; never let it grow unbounded
                await self._deliver(buffer)
                buffer = b""

    async def _deliver(self, raw: bytes) -> None:
        line = _clean(raw)
        if not line.strip():
            return
        self.lines_received += 1
        _LOGGER.debug("SMDR line: %r", line)
        try:
            result = self._on_line(line)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            # The line itself can hold phone numbers; it is only logged at debug level.
            _LOGGER.exception("Error handling an SMDR line (%d characters)", len(line))
