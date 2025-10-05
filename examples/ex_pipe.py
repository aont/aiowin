import asyncio
from win_asyncio_io import create_pipe_pair, ensure_proactor_loop

async def main():
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    ensure_proactor_loop()

    r, w = await create_pipe_pair()
    await w.write(b"test")
    # パイプ終端を閉じる
    await w.aclose()
    data = await r.read()
    print("PIPE:", data)
    await r.aclose()

asyncio.run(main())
