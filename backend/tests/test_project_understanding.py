import json

from gva.agents.project_understanding import _sanitize_insight_payload


def test_sanitize_insight_payload_stringifies_architecture_object() -> None:
    payload = {
        "architecture": {"modules": {"app.py": "UI entry"}},
        "evidence": {"architecture": "README.md"},
    }

    sanitized = _sanitize_insight_payload(payload)

    assert json.loads(sanitized["architecture"])["modules"]["app.py"] == "UI entry"
    assert sanitized["evidence"]["architecture"] == ["README.md"]
