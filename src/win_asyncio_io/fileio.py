import asyncio
import asyncio.proactor_events
import asyncio.windows_utils

from .utils import ensure_proactor_loop
from . import winapi
from .pipe import _make_writer_protocol, _TransportBoundStreamReader, _TransportClosingStreamWriter

# Desired defaults mirror your sample:
#  - READ: OPEN_EXISTING, FILE_FLAG_OVERLAPPED
#  - WRITE: CREATE_ALWAYS, FILE_FLAG_OVERLAPPED


class AsyncFileReader(_TransportBoundStreamReader):
    """StreamReader subclass that tracks the remaining file size."""
    def __init__(self, file_size: int, *, limit: int | None = None):
        super().__init__(limit=limit)
        self._remaining = max(file_size, 0)

    @property
    def remaining(self) -> int:
        """Number of bytes left to consume from the file."""

        return self._remaining

    def _translate_size(self, n: int | None) -> int:
        if self._remaining == 0:
            return 0
        size = super()._translate_size(n)
        if size == -1:
            return self._remaining
        return max(min(size, self._remaining), 0)

    async def _after_read(self, nbytes: int) -> None:
        if self._remaining > 0:
            self._remaining = max(self._remaining - nbytes, 0)
        await super()._after_read(nbytes)
        if self._remaining == 0:
            await self.aclose()

    async def read(self, n: int | None = -1) -> bytes:  # type: ignore[override]
        if self._remaining == 0:
            await self.aclose()
            return b""
        return await super().read(n if n is not None else -1)


class AsyncFileWriter(_TransportClosingStreamWriter):
    """StreamWriter subclass for overlapped file handles."""

DEFAULT_SHARE_FLAGS = (
    winapi.FILE_SHARE_READ | winapi.FILE_SHARE_WRITE | winapi.FILE_SHARE_DELETE
)


async def open_async_reader(path: str, share_mode: int = DEFAULT_SHARE_FLAGS) -> AsyncFileReader:
    """
    Open a file for async READ using overlapped I/O and connect_read_pipe, like the sample.

    Returns an :class:`AsyncFileReader`, a :class:`asyncio.StreamReader` subclass that
    automatically closes the underlying transport once the file has been fully consumed.

    share_mode: typically 0. Use constants from ``win_asyncio_io.winapi`` when sharing is required.
    """
    ensure_proactor_loop()
    loop = asyncio.get_running_loop()
    osfhandle = winapi.CreateFile(
        path,
        winapi.GENERIC_READ,
        share_mode,
        0,
        winapi.OPEN_EXISTING,
        winapi.FILE_FLAG_OVERLAPPED,
        0,
    )
    if osfhandle == winapi.INVALID_HANDLE_VALUE:
        raise OSError(f"CreateFile(read, {path!r}) failed")
    rph = asyncio.windows_utils.PipeHandle(osfhandle)
    file_size = winapi.GetFileSizeEx(osfhandle)
    reader = AsyncFileReader(file_size)
    protocol = asyncio.StreamReaderProtocol(reader)
    transport, _ = await loop.connect_read_pipe(lambda: protocol, rph)
    reader.bind_transport(transport)
    return reader

async def open_async_writer(
    path: str,
    create_disposition: int = 2,  # CREATE_ALWAYS
    share_mode: int = DEFAULT_SHARE_FLAGS,
) -> AsyncFileWriter:
    """
    Open a file for async WRITE using overlapped I/O and _ProactorBaseWritePipeTransport.

    Returns an :class:`AsyncFileWriter`, a :class:`asyncio.StreamWriter` subclass exposing an
    ``aclose`` coroutine as well as a convenience ``write`` coroutine that writes and drains.
    """
    ensure_proactor_loop()
    loop = asyncio.get_running_loop()
    osfhandle = winapi.CreateFile(
        path,
        winapi.GENERIC_WRITE,
        share_mode,
        0,
        create_disposition,
        winapi.FILE_FLAG_OVERLAPPED,
        0,
    )
    if osfhandle == winapi.INVALID_HANDLE_VALUE:
        raise OSError(f"CreateFile(write, {path!r}) failed")
    wph = asyncio.windows_utils.PipeHandle(osfhandle)

    # Writer transport via private API (same as your sample)
    waiter = loop.create_future()
    wproto = _make_writer_protocol(loop)
    wtransport = asyncio.proactor_events._ProactorBaseWritePipeTransport(  # type: ignore[attr-defined]
        sock=wph, protocol=wproto, loop=loop, waiter=waiter, extra=None
    )
    await waiter
    writer = AsyncFileWriter(wtransport, wproto, loop)
    return writer
