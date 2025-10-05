import asyncio
import os
import pytest
from win_asyncio_io import open_async_reader, open_async_writer

pytestmark = pytest.mark.skipif(__import__("sys").platform != "win32", reason="Windows only")

@pytest.mark.asyncio
async def test_file_read_write(tmp_path):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    p = tmp_path / "x.txt"
    w = await open_async_writer(str(p))
    await w.write(b"hello")
    await w.aclose()

    r = await open_async_reader(str(p))
    data = await r.read()
    await r.aclose()
    assert data == b"hello"
