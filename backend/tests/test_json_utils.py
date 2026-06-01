from gva.core.json_utils import loads_json_object


def test_loads_json_object_from_fenced_block() -> None:
    assert loads_json_object('```json\n{"ok": true}\n```') == {"ok": True}
