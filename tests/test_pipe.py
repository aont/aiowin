import asyncio
import pytest
from win_asyncio_io import create_pipe_pair

pytestmark = pytest.mark.skipif(__import__("sys").platform != "win32", reason="Windows only")

@pytest.mark.asyncio
async def test_pipe_roundtrip():
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    r, w = await create_pipe_pair()
    payload = b"test-12345"
    w.write(payload)
    await w.drain()
    await w.aclose()
    data = await r.read()
    await r.aclose()
    assert data == payload
