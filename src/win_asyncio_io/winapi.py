"""Minimal Win32 API helpers implemented via :mod:`ctypes`.

This module exposes just enough of the Windows file/event API surface used by
``win_asyncio_io`` without relying on CPython's private ``_winapi`` module or
the external ``pywin32`` package.  The functions are thin wrappers around the
corresponding ``kernel32`` exports and return plain Python integers for handle
values so the rest of the code can keep working unchanged.

The module is intentionally Windows-only – importing it on any other platform
will raise ``RuntimeError`` just like the original helpers in this project.
"""

from __future__ import annotations

import sys

if sys.platform != "win32":  # pragma: no cover - module is Windows specific
    raise RuntimeError("win_asyncio_io.winapi is available on Windows only")

import ctypes
import ctypes.wintypes as wt


# ``ctypes`` only exposes ``WinDLL``/``windll`` on Windows.  ``use_last_error``
# ensures ``ctypes.get_last_error()`` mirrors ``GetLastError`` like the builtin
# ``_winapi`` module.
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def _to_c_bool(value: bool) -> wt.BOOL:
    return wt.BOOL(1 if value else 0)


def _maybe_pointer(value: int | None) -> ctypes.c_void_p | None:
    return None if not value else ctypes.c_void_p(value)


def _handle_value(handle: wt.HANDLE | int | None) -> int:
    """Return ``handle`` as a Python integer."""

    if isinstance(handle, int):
        return handle
    if handle is None:
        return 0
    return int(handle.value) if handle.value is not None else 0


# Win32 constants we rely on -------------------------------------------------

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000

FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004

OPEN_EXISTING = 3

FILE_FLAG_OVERLAPPED = 0x40000000

STD_INPUT_HANDLE = -10 & 0xFFFFFFFF  # DWORD representation of (DWORD)-10

INVALID_HANDLE_VALUE = ctypes.c_size_t(-1).value


# Function prototypes --------------------------------------------------------

_CreateFileW = kernel32.CreateFileW
_CreateFileW.argtypes = [
    wt.LPCWSTR,
    wt.DWORD,
    wt.DWORD,
    wt.LPVOID,
    wt.DWORD,
    wt.DWORD,
    wt.HANDLE,
]
_CreateFileW.restype = wt.HANDLE

_CreateFileA = kernel32.CreateFileA
_CreateFileA.argtypes = [
    wt.LPCSTR,
    wt.DWORD,
    wt.DWORD,
    wt.LPVOID,
    wt.DWORD,
    wt.DWORD,
    wt.HANDLE,
]
_CreateFileA.restype = wt.HANDLE

_GetStdHandle = kernel32.GetStdHandle
_GetStdHandle.argtypes = [wt.DWORD]
_GetStdHandle.restype = wt.HANDLE

_GetFileType = kernel32.GetFileType
_GetFileType.argtypes = [wt.HANDLE]
_GetFileType.restype = wt.DWORD

_CloseHandle = kernel32.CloseHandle
_CloseHandle.argtypes = [wt.HANDLE]
_CloseHandle.restype = wt.BOOL

_CreateEventW = kernel32.CreateEventW
_CreateEventW.argtypes = [wt.LPVOID, wt.BOOL, wt.BOOL, wt.LPCWSTR]
_CreateEventW.restype = wt.HANDLE

_CreateEventA = kernel32.CreateEventA
_CreateEventA.argtypes = [wt.LPVOID, wt.BOOL, wt.BOOL, wt.LPCSTR]
_CreateEventA.restype = wt.HANDLE

_SetEvent = kernel32.SetEvent
_SetEvent.argtypes = [wt.HANDLE]
_SetEvent.restype = wt.BOOL

_ResetEvent = kernel32.ResetEvent
_ResetEvent.argtypes = [wt.HANDLE]
_ResetEvent.restype = wt.BOOL


# Public API -----------------------------------------------------------------

def CreateFile(
    filename: str | bytes,
    desired_access: int,
    share_mode: int,
    security_attributes: int | None,
    creation_disposition: int,
    flags_and_attributes: int,
    template_file: int | None,
) -> int:
    """Call ``CreateFile`` and return the handle as ``int``."""

    if isinstance(filename, bytes):
        handle = _CreateFileA(
            filename,
            desired_access,
            share_mode,
            _maybe_pointer(security_attributes),
            creation_disposition,
            flags_and_attributes,
            wt.HANDLE(template_file or 0),
        )
    else:
        handle = _CreateFileW(
            filename,
            desired_access,
            share_mode,
            _maybe_pointer(security_attributes),
            creation_disposition,
            flags_and_attributes,
            wt.HANDLE(template_file or 0),
        )
    return _handle_value(handle)


def GetStdHandle(std_handle: int) -> int:
    return _handle_value(_GetStdHandle(wt.DWORD(std_handle)))


def GetFileType(handle: int) -> int:
    return int(_GetFileType(wt.HANDLE(handle)))


def CloseHandle(handle: int) -> None:
    if handle and handle != INVALID_HANDLE_VALUE:
        _CloseHandle(wt.HANDLE(handle))


def CreateEvent(
    security_attributes: int | None,
    manual_reset: bool,
    initial_state: bool,
    name: str | bytes | None,
) -> int:
    if isinstance(name, bytes):
        handle = _CreateEventA(
            _maybe_pointer(security_attributes),
            _to_c_bool(manual_reset),
            _to_c_bool(initial_state),
            name,
        )
    else:
        handle = _CreateEventW(
            _maybe_pointer(security_attributes),
            _to_c_bool(manual_reset),
            _to_c_bool(initial_state),
            name,
        )
    return _handle_value(handle)


def SetEvent(handle: int) -> None:
    _SetEvent(wt.HANDLE(handle))


def ResetEvent(handle: int) -> None:
    _ResetEvent(wt.HANDLE(handle))


__all__ = [
    "GENERIC_READ",
    "GENERIC_WRITE",
    "FILE_SHARE_READ",
    "FILE_SHARE_WRITE",
    "FILE_SHARE_DELETE",
    "OPEN_EXISTING",
    "FILE_FLAG_OVERLAPPED",
    "STD_INPUT_HANDLE",
    "INVALID_HANDLE_VALUE",
    "CreateFile",
    "GetStdHandle",
    "GetFileType",
    "CloseHandle",
    "CreateEvent",
    "SetEvent",
    "ResetEvent",
]
