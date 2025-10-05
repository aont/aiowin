import asyncio
import sys
import _winapi
import asyncio.windows_utils
from .utils import (
    FILE_TYPE_CHAR, FILE_TYPE_PIPE,
    ENABLE_ECHO_INPUT, ENABLE_LINE_INPUT,
    get_file_type, get_console_mode, set_console_mode, ConsoleModeGuard,
    ensure_proactor_loop
)

class AsyncStdinReader:
    """
    Async context manager that exposes Windows stdin as asyncio.StreamReader.

    - If stdin is a console: open 'CONIN$' with FILE_FLAG_OVERLAPPED and (optionally) disable
      LINE_INPUT / ECHO_INPUT to get raw-ish behavior, exactly like the original snippet.
    - If stdin is a pipe: wrap the existing STDIN handle with PipeHandle and connect_read_pipe.

    Usage:
        async with AsyncStdinReader(raw_console=True) as reader:
            data = await reader.read(1024)
    """
    def __init__(self, raw_console: bool = True):
        self._raw_console = raw_console
        self._reader: asyncio.StreamReader | None = None
        self._transport = None
        self._console_guard: ConsoleModeGuard | None = None
        self._opened_handle: int | None = None  # CONIN$ handle when opened, else None

    @property
    def reader(self) -> asyncio.StreamReader:
        assert self._reader is not None
        return self._reader

    async def __aenter__(self) -> asyncio.StreamReader:
        ensure_proactor_loop()
        loop = asyncio.get_running_loop()
        stdin_handle = _winapi.GetStdHandle(_winapi.STD_INPUT_HANDLE)
        ftype = get_file_type(stdin_handle)

        if ftype == FILE_TYPE_CHAR:
            # Console: adjust mode if requested and open CONIN$ overlapped.
            if self._raw_console:
                mode = get_console_mode(stdin_handle)
                new_mode = mode & ~ENABLE_LINE_INPUT & ~ENABLE_ECHO_INPUT
                self._console_guard = ConsoleModeGuard(stdin_handle, new_mode)
                self._console_guard.__enter__()
            conin = _winapi.CreateFile(
                "CONIN$",
                _winapi.GENERIC_READ,
                0, 0,
                _winapi.OPEN_EXISTING,
                _winapi.FILE_FLAG_OVERLAPPED,
                0
            )
            if int(conin) == _winapi.INVALID_HANDLE_VALUE:
                raise OSError("CreateFile(CONIN$) failed")
            self._opened_handle = conin
            rph = asyncio.windows_utils.PipeHandle(conin)
        elif ftype == FILE_TYPE_PIPE:
            rph = asyncio.windows_utils.PipeHandle(stdin_handle)
        else:
            # As a last resort, try treating it like a pipe (rare).
            rph = asyncio.windows_utils.PipeHandle(stdin_handle)

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport, _ = await loop.connect_read_pipe(lambda: protocol, rph)
        self._reader = reader
        self._transport = transport
        return reader

    async def __aexit__(self, exc_type, exc, tb):
        if self._transport is not None:
            self._transport.close()
            # not all transports expose wait_closed on Windows read pipe, so guard it
            wait_closed = getattr(self._transport, "wait_closed", None)
            if wait_closed is not None:
                await wait_closed()
        if self._console_guard is not None:
            self._console_guard.__exit__(exc_type, exc, tb)
        # PipeHandle closes underlying handle when Transport is closed; nothing else to do.
