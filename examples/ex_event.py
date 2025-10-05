import asyncio
from win_asyncio_io import AsyncWin32Event, ensure_proactor_loop

async def main():
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    ensure_proactor_loop()

    ev = AsyncWin32Event(manual_reset=False, initial_state=False)

    async def setter():
        await asyncio.sleep(1.5)
        ev.set()

    asyncio.create_task(setter())
    await ev.wait()  # Event シグナルを await
    print("Event signaled")

asyncio.run(main())
