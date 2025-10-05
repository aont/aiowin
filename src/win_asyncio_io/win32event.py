import asyncio
import sys
import win32event  # from pywin32
from typing import Iterable
from .utils import ensure_proactor_loop

class AsyncWin32Event:
    """
    Thin wrapper around a Win32 Event handle that can be awaited via IocpProactor.wait_for_handle,
    exactly like the provided sample.
    """
    def __init__(self, manual_reset: bool = False, initial_state: bool = False, name: str | None = None):
        self._handle = win32event.CreateEvent(None, manual_reset, initial_state, name)

    @property
    def handle(self) -> int:
        return int(self._handle)

    def set(self) -> None:
        win32event.SetEvent(self._handle)

    def reset(self) -> None:
        win32event.ResetEvent(self._handle)

    def close(self) -> None:
        win32event.CloseHandle(self._handle)

    async def wait(self, timeout: float | None = None) -> None:
        """
        Await signal. timeout is seconds or None.
        """
        ensure_proactor_loop()
        loop = asyncio.get_running_loop()
        proactor = getattr(loop, "_proactor", None)
        fut = proactor.wait_for_handle(self.handle, timeout)
        await fut

async def wait_many(events: Iterable["AsyncWin32Event"]) -> "AsyncWin32Event":
    """
    Wait until any event is signaled and return it (FIRST_COMPLETED).
    """
    ensure_proactor_loop()
    tasks = [asyncio.create_task(ev.wait()) for ev in events]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    # determine which event completed
    winner_idx = next(i for i, t in enumerate(tasks) if t in done)
    # cancel others
    for i, t in enumerate(tasks):
        if i != winner_idx:
            t.cancel()
    return list(events)[winner_idx]
