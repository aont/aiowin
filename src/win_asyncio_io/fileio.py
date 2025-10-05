import asyncio
import asyncio.proactor_events
import asyncio.windows_utils
import _winapi
from .utils import ensure_proactor_loop
from .pipe import _make_writer_protocol

# Desired defaults mirror your sample:
#  - READ: OPEN_EXISTING, FILE_FLAG_OVERLAPPED
#  - WRITE: CREATE_ALWAYS, FILE_FLAG_OVERLAPPED

class AsyncFileReader:
    def __init__(self, reader: asyncio.StreamReader, transport: asyncio.BaseTransport):
        self.reader = reader
        self.transport = transport

    async def read(self, n: int | None = None) -> bytes:
        if n is None:
            return await self.reader.read()
        return await self.reader.read(n)

    async def aclose(self) -> None:
        try:
            self.transport.close()
        finally:
            wait_closed = getattr(self.transport, "wait_closed", None)
            if wait_closed is not None:
                await wait_closed()

class AsyncFileWriter:
    def __init__(self, writer: asyncio.StreamWriter, transport: asyncio.BaseTransport):
        self.writer = writer
        self.transport = transport

    async def write(self, data: bytes) -> None:
        self.writer.write(data)
        await self.writer.drain()

    async def aclose(self) -> None:
        try:
            self.writer.close()
        finally:
            wait_closed = getattr(self.transport, "wait_closed", None)
            if wait_closed is not None:
                await wait_closed()

async def open_async_reader(path: str, share_mode: int = 0) -> AsyncFileReader:
    """
    Open a file for async READ using overlapped I/O and connect_read_pipe, like the sample.

    share_mode: typically 0. Use win32file.FILE_SHARE_READ if必要なら（pywin32が提供）。
    """
    ensure_proactor_loop()
    loop = asyncio.get_running_loop()
    osfhandle = _winapi.CreateFile(
        path,
        _winapi.GENERIC_READ,
        share_mode,
        0,
        _winapi.OPEN_EXISTING,
        _winapi.FILE_FLAG_OVERLAPPED,
        0,
    )
    if int(osfhandle) == _winapi.INVALID_HANDLE_VALUE:
        raise OSError(f"CreateFile(read, {path!r}) failed")
    rph = asyncio.windows_utils.PipeHandle(osfhandle)
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    transport, _ = await loop.connect_read_pipe(lambda: protocol, rph)
    return AsyncFileReader(reader, transport)

async def open_async_writer(
    path: str,
    create_disposition: int = 2,  # CREATE_ALWAYS
    share_mode: int = 0
) -> AsyncFileWriter:
    """
    Open a file for async WRITE using overlapped I/O and _ProactorBaseWritePipeTransport.
    """
    ensure_proactor_loop()
    loop = asyncio.get_running_loop()
    osfhandle = _winapi.CreateFile(
        path,
        _winapi.GENERIC_WRITE,
        share_mode,
        0,
        create_disposition,
        _winapi.FILE_FLAG_OVERLAPPED,
        0,
    )
    if int(osfhandle) == _winapi.INVALID_HANDLE_VALUE:
        raise OSError(f"CreateFile(write, {path!r}) failed")
    wph = asyncio.windows_utils.PipeHandle(osfhandle)

    # Writer transport via private API (same as your sample)
    waiter = loop.create_future()
    wproto = _make_writer_protocol(loop)   # <- 修正点
    wtransport = asyncio.proactor_events._ProactorBaseWritePipeTransport(  # type: ignore[attr-defined]
        sock=wph, protocol=wproto, loop=loop, waiter=waiter, extra=None
    )
    await waiter
    writer = asyncio.streams.StreamWriter(wtransport, wproto, None, loop)
    return AsyncFileWriter(writer, wtransport)
