"""Utilities for awaiting Win32 event handles with asyncio."""

from __future__ import annotations

import asyncio

from .utils import ensure_proactor_loop


async def wait_for_handle(handle: int | object, timeout: float | None = None) -> None:
    """Await a Win32 handle becoming signalled.

    Parameters
    ----------
    handle:
        A Win32 handle value (typically obtained via :mod:`ctypes`).  The value
        is converted to ``int`` before being passed to the underlying proactor.
    timeout:
        Optional timeout in seconds.  ``None`` waits indefinitely.
    """

    ensure_proactor_loop()
    loop = asyncio.get_running_loop()
    proactor = getattr(loop, "_proactor", None)
    if proactor is None:
        raise RuntimeError("The running event loop is not backed by a proactor")

    await proactor.wait_for_handle(int(handle), timeout)


__all__ = ["wait_for_handle"]
