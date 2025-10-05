import sys
import asyncio
import ctypes

if sys.platform != "win32":
    raise RuntimeError("win-asyncio-io is Windows-only")

import ctypes.wintypes as wt

from . import winapi

# --- Win32 helpers -----------------------------------------------------------

kernel32 = winapi.kernel32

# Console mode bits
ENABLE_LINE_INPUT = 0x0002
ENABLE_ECHO_INPUT = 0x0004

FILE_TYPE_UNKNOWN = 0x0000
FILE_TYPE_DISK    = 0x0001
FILE_TYPE_CHAR    = 0x0002
FILE_TYPE_PIPE    = 0x0003

def _to_handle(h: int) -> wt.HANDLE:
    return wt.HANDLE(int(h))

def get_file_type(handle: int) -> int:
    return winapi.GetFileType(handle)

def get_console_mode(handle: int) -> int:
    mode = wt.DWORD()
    if not kernel32.GetConsoleMode(_to_handle(handle), ctypes.byref(mode)):
        raise OSError(ctypes.get_last_error(), "GetConsoleMode failed")
    return mode.value

def set_console_mode(handle: int, mode: int) -> None:
    if not kernel32.SetConsoleMode(_to_handle(handle), wt.DWORD(mode)):
        raise OSError(ctypes.get_last_error(), "SetConsoleMode failed")

def close_handle(handle: int) -> None:
    if handle and int(handle) != 0 and int(handle) != winapi.INVALID_HANDLE_VALUE:
        winapi.CloseHandle(handle)

class ConsoleModeGuard:
    """
    Set console mode on __enter__ and restore on __exit__.
    """
    def __init__(self, handle: int, new_mode: int):
        self.handle = handle
        self.old_mode = None
        self.new_mode = new_mode

    def __enter__(self):
        self.old_mode = get_console_mode(self.handle)
        set_console_mode(self.handle, self.new_mode)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.old_mode is not None:
            try:
                set_console_mode(self.handle, self.old_mode)
            except Exception:
                # best-effort restore
                pass

def ensure_proactor_loop(loop: asyncio.AbstractEventLoop | None = None) -> None:
    """
    Ensure the running loop is backed by IocpProactor (Windows Proactor loop).
    Mirrors the original code's reliance on loop._proactor and private transports.
    """
    loop = loop or asyncio.get_event_loop()
    proactor = getattr(loop, "_proactor", None)
    try:
        from asyncio.windows_events import IocpProactor  # type: ignore
    except Exception as e:
        raise RuntimeError("This environment lacks asyncio.windows_events.IocpProactor") from e
    if not isinstance(proactor, IocpProactor):
        raise RuntimeError(
            "This package requires a Proactor-based event loop "
            "(WindowsProactorEventLoopPolicy)."
        )
