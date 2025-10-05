import asyncio
import asyncio.proactor_events
import asyncio.windows_utils
import _winapi
from typing import NamedTuple
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

class AsyncPipeReader(NamedTuple):
    reader: asyncio.StreamReader
    transport: asyncio.BaseTransport

class AsyncPipeWriter:
    def __init__(self, writer: asyncio.StreamWriter, transport: asyncio.BaseTransport):
        self.writer = writer
        self.transport = transport

    async def write(self, data: bytes) -> None:
        self.writer.write(data)
        await self.writer.drain()

    async def aclose(self) -> None:
        try:
            self.writer.close()
        except Exception:
            pass
        wait_closed = getattr(self.transport, "wait_closed", None)
        if wait_closed is not None:
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
