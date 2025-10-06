import asyncio
import ctypes
import ctypes.wintypes as wt

import pytest

from win_asyncio_io import ensure_proactor_loop, wait_for_handle

pytestmark = pytest.mark.skipif(__import__("sys").platform != "win32", reason="Windows only")

@pytest.mark.asyncio
async def test_event_wait():
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    ensure_proactor_loop()

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateEventW.argtypes = [wt.LPVOID, wt.BOOL, wt.BOOL, wt.LPCWSTR]
    kernel32.CreateEventW.restype = wt.HANDLE
    kernel32.SetEvent.argtypes = [wt.HANDLE]
    kernel32.SetEvent.restype = wt.BOOL
    kernel32.CloseHandle.argtypes = [wt.HANDLE]
    kernel32.CloseHandle.restype = wt.BOOL

    event = kernel32.CreateEventW(None, False, False, None)
    if not event:
        raise ctypes.WinError(ctypes.get_last_error())

    async def setter():
        await asyncio.sleep(0.2)
        kernel32.SetEvent(event)

    try:
        asyncio.create_task(setter())
        await wait_for_handle(event)
    finally:
        kernel32.CloseHandle(event)
