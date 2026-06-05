import asyncio

from gva.core.asyncio_windows import install_windows_connection_reset_filter, is_windows_connection_reset


def test_windows_connection_reset_detection_accepts_errno_10054() -> None:
    assert is_windows_connection_reset(ConnectionResetError(10054, "reset"))
    assert not is_windows_connection_reset(ConnectionResetError(104, "reset"))
    assert not is_windows_connection_reset(RuntimeError("reset"))


def test_windows_connection_reset_filter_only_swallows_10054() -> None:
    loop = asyncio.new_event_loop()
    calls: list[dict] = []

    def previous(_loop, context):
        calls.append(context)

    try:
        loop.set_exception_handler(previous)
        install_windows_connection_reset_filter(loop)
        handler = loop.get_exception_handler()
        assert handler is not None

        handler(loop, {"exception": ConnectionResetError(10054, "reset")})
        assert calls == []

        error = RuntimeError("real error")
        handler(loop, {"exception": error})
        assert calls == [{"exception": error}]
    finally:
        loop.close()
