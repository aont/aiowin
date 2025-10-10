import asyncio
from win_asyncio_io import open_async_writer, open_async_reader, ensure_proactor_loop

async def main():
    print("Setting WindowsProactorEventLoopPolicy")
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("Ensuring proactor loop is installed")
    ensure_proactor_loop()

    # WRITE
    print("Opening async writer for demo.txt")
    w = await open_async_writer("demo.txt")  # CREATE_ALWAYS 相当
    print("Writing to demo.txt")
    w.write(b"hello overlapped io")
    await w.drain()
    print("Closing writer")
    await w.aclose()

    # READ
    print("Opening async reader for demo.txt")
    r = await open_async_reader("demo.txt")
    print("Reading from demo.txt")
    data = await r.read()
    print("FILE:", data)
    print("Closing reader")
    await r.aclose()

    print("File IO example completed")

asyncio.run(main())
