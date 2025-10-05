import asyncio
import pytest
from win_asyncio_io import AsyncWin32Event

pytestmark = pytest.mark.skipif(__import__("sys").platform != "win32", reason="Windows only")

@pytest.mark.asyncio
async def test_event_wait():
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    ev = AsyncWin32Event()
    async def setter():
        await asyncio.sleep(0.2)
        ev.set()
    asyncio.create_task(setter())
    await ev.wait()
