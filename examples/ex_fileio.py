import asyncio
from win_asyncio_io import open_async_writer, open_async_reader, ensure_proactor_loop

async def main():
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    ensure_proactor_loop()

    # WRITE
    w = await open_async_writer("demo.txt")  # CREATE_ALWAYS 相当
    await w.write(b"hello overlapped io")
    await w.aclose()

    # READ
    r = await open_async_reader("demo.txt")
    data = await r.read()
    print("FILE:", data)
    await r.aclose()

asyncio.run(main())
