# win-asyncio-io

Windows の Proactor / IOCP を**そのまま**使い、`stdin` / `pipe` / `file` / `win32 event`
を asyncio で扱うための極薄ラッパー。実装は以下を忠実に踏襲しています。

- `_winapi.CreateFile(..., FILE_FLAG_OVERLAPPED)`
- `asyncio.windows_utils.PipeHandle`
- `loop.connect_read_pipe` + `StreamReaderProtocol`
- `asyncio.proactor_events._ProactorBaseWritePipeTransport`（私用 API）
- `loop._proactor.wait_for_handle(...)`（私用 API）

> ⚠️ **互換性:** CPython の私用 API に依存します。3.9–3.11 での動作を想定。  
> 3.12+ は breaking の可能性が高く、自己責任でお願いします。

## Install

```bash
pip install .
````

## Policy / Loop

```python
import asyncio
asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
```

## API

* `AsyncStdinReader(raw_console: bool=True)` → `async with` で `StreamReader`
* `create_pipe_pair()` → `(AsyncPipeReader, AsyncPipeWriter)`
* `open_async_reader(path)` / `open_async_writer(path)`
* `AsyncWin32Event` / `wait_many([...])`
