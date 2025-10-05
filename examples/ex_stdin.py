import asyncio
from win_asyncio_io import AsyncStdinReader, ensure_proactor_loop
import asyncio

async def main():
    # Explicitly set on Windows for clarity
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    ensure_proactor_loop()

    async with AsyncStdinReader(raw_console=True) as reader:
        data = await reader.read(10)  # Example: read 10 bytes
        print("READ:", data)

asyncio.run(main())
