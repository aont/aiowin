import asyncio
import asyncio.proactor_events
import asyncio.windows_utils

from .utils import ensure_proactor_loop


class _TransportBoundStreamReader(asyncio.StreamReader):
    """StreamReader that retains and explicitly closes its transport."""

    def __init__(self, *, limit: int | None = None):
        if limit is None:
            super().__init__()
        else:
            super().__init__(limit=limit)
        self._bound_transport: asyncio.BaseTransport | None = None
        self._transport_closed = False

    def bind_transport(self, transport: asyncio.BaseTransport) -> None:
        self._bound_transport = transport

    async def aclose(self) -> None:
        if self._transport_closed:
            return
        self._transport_closed = True
        transport = self._bound_transport
        if transport is None:
            return
        try:
            transport.close()
        finally:
            wait_closed = getattr(transport, "wait_closed", None)
            if callable(wait_closed):
                await wait_closed()

    def _translate_size(self, n: int | None) -> int:
        if n is None:
            return -1
        return n

    async def _after_read(self, nbytes: int) -> None:
        if self.at_eof():
            await self.aclose()

    async def read(self, n: int | None = -1) -> bytes:  # type: ignore[override]
        limit = self._translate_size(n if n is not None else -1)
        data = await super().read(limit)
        await self._after_read(len(data))
        return data

    async def readline(self) -> bytes:  # type: ignore[override]
        data = await super().readline()
        await self._after_read(len(data))
        return data

    async def readexactly(self, n: int) -> bytes:  # type: ignore[override]
        data = await super().readexactly(n)
        await self._after_read(len(data))
        return data


class _TransportClosingStreamWriter(asyncio.StreamWriter):
    """StreamWriter that exposes an ``aclose`` coroutine."""

    def __init__(
        self,
        transport: asyncio.BaseTransport,
        protocol: asyncio.BaseProtocol,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        super().__init__(transport, protocol, None, loop)
        self._close_called = False

    async def write(self, data: bytes) -> None:  # type: ignore[override]
        super().write(data)
        await self.drain()

    def write_nowait(self, data: bytes) -> None:
        super().write(data)

    async def aclose(self) -> None:
        if self._close_called:
            return
        self._close_called = True
        try:
            self.close()
        except Exception:
            pass

        wait_writer = getattr(self, "wait_closed", None)
        if callable(wait_writer):
            try:
                await wait_writer()
            except Exception:
                pass

        transport = self.transport
        if transport is not None:
            try:
                transport.close()
            except Exception:
                pass

            wait_closed = getattr(transport, "wait_closed", None)
            if callable(wait_closed):
                await wait_closed()

def _make_writer_protocol(loop: asyncio.AbstractEventLoop):
    """
    Return a protocol object suitable for passing to _ProactorBaseWritePipeTransport.
    Try to use asyncio.streams.FlowControlMixin(loop) (matches original snippet).
    If that fails for any reason, return a simple fallback protocol implementing
    the minimal API (_transport storage, pause_writing/resume_writing).
    """
    try:
        # original snippet created an *instance* of FlowControlMixin and used it as protocol
        proto = asyncio.streams.FlowControlMixin(loop)
        return proto
    except Exception:
        # fallback: simple protocol that provides the expected methods
        class _FallbackWriterProtocol(asyncio.Protocol):
            def __init__(self, loop):
                self._loop = loop
                self._paused = False
                self._transport = None

            def connection_made(self, transport: asyncio.BaseTransport) -> None:
                self._transport = transport

            def connection_lost(self, exc: Exception | None) -> None:
                pass

            # Flow control hooks expected by transports:
            def pause_writing(self) -> None:
                self._paused = True

            def resume_writing(self) -> None:
                self._paused = False

        return _FallbackWriterProtocol(loop)

class AsyncPipeReader(_TransportBoundStreamReader):
    """StreamReader subclass that keeps the pipe transport alive."""


class AsyncPipeWriter(_TransportClosingStreamWriter):
    """StreamWriter subclass with an ``aclose`` coroutine for pipe writers."""

async def create_pipe_pair() -> tuple[AsyncPipeReader, AsyncPipeWriter]:
    """
    Create an overlapped anonymous pipe pair and wrap as asyncio reader/writer.

    Returns ``(AsyncPipeReader, AsyncPipeWriter)`` where both objects inherit from
    :class:`asyncio.StreamReader` / :class:`asyncio.StreamWriter` respectively and provide an
    ``aclose`` coroutine for deterministic resource cleanup.
    """
    ensure_proactor_loop()
    loop = asyncio.get_running_loop()

    # Anonymous pipe with overlapped I/O (both ends)
    rh, wh = asyncio.windows_utils.pipe(overlapped=(True, True), duplex=False)

    # Reader: connect_read_pipe
    rph = asyncio.windows_utils.PipeHandle(rh)
    reader = AsyncPipeReader()
    rproto = asyncio.StreamReaderProtocol(reader)
    rtransport, _ = await loop.connect_read_pipe(lambda: rproto, rph)
    reader.bind_transport(rtransport)

    # Writer: use instance of FlowControlMixin(loop) if possible (matches original)
    wph = asyncio.windows_utils.PipeHandle(wh)
    wproto = _make_writer_protocol(loop)
    waiter = loop.create_future()
    wtransport = asyncio.proactor_events._ProactorBaseWritePipeTransport(  # type: ignore[attr-defined]
        sock=wph, protocol=wproto, loop=loop, waiter=waiter, extra=None
    )
    await waiter
    writer = AsyncPipeWriter(wtransport, wproto, loop)
    return reader, writer
