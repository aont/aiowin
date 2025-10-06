import asyncio
import ctypes
import ctypes.wintypes as wt

from win_asyncio_io import ensure_proactor_loop, wait_for_handle


kernel32 = ctypes.windll.kernel32
kernel32.CreateEventW.argtypes = [wt.LPVOID, wt.BOOL, wt.BOOL, wt.LPCWSTR]
kernel32.CreateEventW.restype = wt.HANDLE
kernel32.SetEvent.argtypes = [wt.HANDLE]
kernel32.SetEvent.restype = wt.BOOL
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL

async def main():
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    ensure_proactor_loop()

    event = kernel32.CreateEventW(None, False, False, None)
    if not event:
        raise ctypes.WinError(ctypes.get_last_error())

    async def setter():
        await asyncio.sleep(1.5)
        kernel32.SetEvent(event)

    try:
        asyncio.create_task(setter())
        await wait_for_handle(event)  # Await the event signal
        print("Event signaled")
    finally:
        kernel32.CloseHandle(event)

asyncio.run(main())
