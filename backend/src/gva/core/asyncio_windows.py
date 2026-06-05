from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any


ExceptionHandler = Callable[[asyncio.AbstractEventLoop, dict[str, Any]], None]


def install_windows_connection_reset_filter(loop: asyncio.AbstractEventLoop | None = None) -> None:
    """Silence noisy WinError 10054 callbacks from Windows asyncio transports."""
    active_loop = loop or asyncio.get_running_loop()
    previous = active_loop.get_exception_handler()
    if getattr(previous, "_gva_windows_reset_filter", False):
        return

    def handler(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        if is_windows_connection_reset(context.get("exception")):
            return
        if previous is not None:
            previous(event_loop, context)
            return
        event_loop.default_exception_handler(context)

    setattr(handler, "_gva_windows_reset_filter", True)
    active_loop.set_exception_handler(handler)


def is_windows_connection_reset(exception: object) -> bool:
    if not isinstance(exception, ConnectionResetError):
        return False
    return getattr(exception, "winerror", None) == 10054 or getattr(exception, "errno", None) == 10054
