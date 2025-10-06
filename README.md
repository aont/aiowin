# win-asyncio-io

An ultra-thin wrapper that uses Windows Proactor/IOCP **as-is** so you can
handle `stdin`, `pipe`, `file`, and `win32 event` handles with asyncio. The
implementation closely follows the following pieces:

- `win_asyncio_io.winapi.CreateFile(..., FILE_FLAG_OVERLAPPED)`
- `asyncio.windows_utils.PipeHandle`
- `loop.connect_read_pipe` + `StreamReaderProtocol`
- `asyncio.proactor_events._ProactorBaseWritePipeTransport` (private API)
- `loop._proactor.wait_for_handle(...)` (private API)

> ⚠️ **Compatibility:** Relies on private CPython APIs and targets CPython
> 3.9–3.11. Version 3.12+ is likely to break; use at your own risk.

## Install

```bash
pip install .
```

## Policy / Loop

```python
import asyncio
asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
```

## API

* `AsyncStdinReader(raw_console: bool=True)` → use with `async with` to get a
  `StreamReader`
* `create_pipe_pair()` → returns `(AsyncPipeReader, AsyncPipeWriter)`
* `open_async_reader(path)` / `open_async_writer(path)`
* `wait_for_handle(handle, timeout=None)`
