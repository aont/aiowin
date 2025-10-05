import asyncio
import asyncio.proactor_events
import asyncio.windows_utils

from .utils import ensure_proactor_loop

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

class AsyncPipeReader:
    """Wrapper around a :class:`asyncio.StreamReader` backed by a pipe.

    The ``connect_read_pipe`` transport keeps the OS handle alive until it is
    explicitly closed.  The original sample code returned the bare
    ``StreamReader`` and relied on the garbage collector to dispose the
    transport which triggered noisy ``ResourceWarning`` messages on Windows.

    Expose a small dedicated wrapper so callers can explicitly close the
    transport once they are done consuming data.  ``reader`` is retained for
    backward compatibility with the earlier ``NamedTuple`` API.
    """

    def __init__(self, reader: asyncio.StreamReader, transport: asyncio.BaseTransport):
        self.reader = reader
        self.transport = transport
        self._closed = False

    async def read(self, n: int | None = None) -> bytes:
        if n is None:
            data = await self.reader.read()
        else:
            data = await self.reader.read(n)
        if self.reader.at_eof():
            await self.aclose()
        return data

    async def readline(self) -> bytes:
        data = await self.reader.readline()
        if self.reader.at_eof():
            await self.aclose()
        return data

    async def readexactly(self, n: int) -> bytes:
        data = await self.reader.readexactly(n)
        if self.reader.at_eof():
            await self.aclose()
        return data

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.transport.close()
        finally:
            wait_closed = getattr(self.transport, "wait_closed", None)
            if callable(wait_closed):
                await wait_closed()

class AsyncPipeWriter:
    def __init__(self, writer: asyncio.StreamWriter, transport: asyncio.BaseTransport):
        self.writer = writer
        self.transport = transport

    async def write(self, data: bytes) -> None:
        self.writer.write(data)
        await self.writer.drain()

    async def aclose(self) -> None:
        """Close the writer transport and wait until the handle is released."""

        # ``StreamWriter.close`` delegates to ``transport.close`` but does not
        # provide a direct awaitable.  Call both defensively and await the
        # transport/stream closures when available so the overlapped handle is
        # released before returning.
        try:
            self.writer.close()
        except Exception:
            pass

        writer_wait_closed = getattr(self.writer, "wait_closed", None)
        if callable(writer_wait_closed):
            try:
                await writer_wait_closed()
            except Exception:
                pass

        try:
            self.transport.close()
        except Exception:
            pass

        wait_closed = getattr(self.transport, "wait_closed", None)
        if callable(wait_closed):
            await wait_closed()

async def create_pipe_pair() -> tuple[AsyncPipeReader, AsyncPipeWriter]:
    """
    Create an overlapped anonymous pipe pair and wrap as asyncio reader/writer.

    Returns:
        (AsyncPipeReader, AsyncPipeWriter)
    """
    ensure_proactor_loop()
    loop = asyncio.get_running_loop()

    # Anonymous pipe with overlapped I/O (both ends)
    rh, wh = asyncio.windows_utils.pipe(overlapped=(True, True), duplex=False)

    # Reader: connect_read_pipe
    rph = asyncio.windows_utils.PipeHandle(rh)
    reader = asyncio.StreamReader()
    rproto = asyncio.StreamReaderProtocol(reader)
    rtransport, _ = await loop.connect_read_pipe(lambda: rproto, rph)
    r = AsyncPipeReader(reader=reader, transport=rtransport)

    # Writer: use instance of FlowControlMixin(loop) if possible (matches original)
    wph = asyncio.windows_utils.PipeHandle(wh)
    wproto = _make_writer_protocol(loop)
    waiter = loop.create_future()
    wtransport = asyncio.proactor_events._ProactorBaseWritePipeTransport(  # type: ignore[attr-defined]
        sock=wph, protocol=wproto, loop=loop, waiter=waiter, extra=None
    )
    await waiter
    writer = asyncio.streams.StreamWriter(wtransport, wproto, None, loop)
    w = AsyncPipeWriter(writer=writer, transport=wtransport)
    return r, w
