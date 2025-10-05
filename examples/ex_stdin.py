import asyncio
from win_asyncio_io import AsyncStdinReader, ensure_proactor_loop
import asyncio

async def main():
    # Windows では念のため明示
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    ensure_proactor_loop()

    async with AsyncStdinReader(raw_console=True) as reader:
        data = await reader.read(10)  # 例: 10 バイト読む
        print("READ:", data)

asyncio.run(main())
