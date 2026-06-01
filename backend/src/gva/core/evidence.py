from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from gva.models.evidence import EvidenceIndex, EvidenceItem
from gva.models.insight import ProjectInsight
from gva.models.repo import RepoFile, RepoSummary


SETUP_RE = re.compile(
    r"\b(install|installation|setup|quickstart|requirements|conda|pip|npm|pnpm|yarn|docker|venv|api key)\b",
    re.IGNORECASE,
)


def build_evidence_index(
    repo: RepoSummary,
    output_dir: Path,
    insight: ProjectInsight | None = None,
) -> EvidenceIndex:
    items: list[EvidenceItem] = []

    for file in repo.files:
        excerpt = _compact_excerpt(file)
        if not excerpt:
            continue
        item_id = _file_item_id(file)
        items.append(
            EvidenceItem(
                id=item_id,
                source_path=file.path,
                role=file.role,
                excerpt=excerpt,
                derived_facts=_derive_facts(file),
            )
        )

    if insight is not None:
        for key, values in insight.evidence.items():
            text = "\n".join(str(value) for value in values if str(value).strip())
            if not text:
                continue
            items.append(
                EvidenceItem(
                    id=_normalize_id(key),
                    source_path="project-insight.json",
                    role="insight",
                    excerpt=text[:900],
                    derived_facts=[_clean_fact(text)[:180]],
                )
            )

    index = EvidenceIndex(repo_name=repo.repo_name, items=_dedupe_items(items))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "repo-evidence-index.json").write_text(
        index.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return index


def evidence_refs_for_keys(keys: list[str], index: EvidenceIndex) -> list[str]:
    if not keys:
        return []
    ids = {item.id for item in index.items}
    normalized = [_normalize_id(key) for key in keys]
    refs = [key for key in normalized if key in ids]
    if refs:
        return list(dict.fromkeys(refs))

    lowered_paths = {item.source_path.lower(): item.id for item in index.items}
    for key in normalized:
        for source_path, item_id in lowered_paths.items():
            if key in source_path or source_path.endswith(key):
                refs.append(item_id)
    return list(dict.fromkeys(refs))


def safe_fallback_refs(index: EvidenceIndex, limit: int = 2) -> list[str]:
    preferred_roles = {"readme", "entry", "source", "config", "doc", "insight"}
    refs = [item.id for item in index.items if item.role in preferred_roles]
    return refs[:limit]


def _compact_excerpt(file: RepoFile) -> str:
    lines: list[str] = []
    in_code = False
    for raw_line in file.excerpt.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if file.role in {"readme", "doc"} and (in_code or SETUP_RE.search(line)):
            continue
        if line:
            lines.append(line)
        if len("\n".join(lines)) > 1000:
            break
    return "\n".join(lines)[:1200]


def _derive_facts(file: RepoFile) -> list[str]:
    facts: list[str] = []
    path = file.path
    if file.role == "readme":
        facts.append(f"{path} contains the project description and public-facing explanation.")
    elif file.role == "config":
        facts.append(f"{path} indicates project configuration or dependency choices.")
    elif file.role == "entry":
        facts.append(f"{path} appears to be an entry point.")
    elif file.role == "source":
        facts.append(f"{path} contains implementation code.")

    if file.language:
        facts.append(f"Language detected from {path}: {file.language}.")
    return facts


def _file_item_id(file: RepoFile) -> str:
    base = _normalize_id(file.path)
    digest = hashlib.sha1(file.path.encode("utf-8")).hexdigest()[:6]
    return f"{base}-{digest}"


def _normalize_id(value: str) -> str:
    lowered = value.strip().lower().replace("\\", "/")
    normalized = re.sub(r"[^a-z0-9/_-]+", "-", lowered)
    normalized = normalized.strip("-/")
    return normalized.replace("/", "-")[:80] or "evidence"


def _clean_fact(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _dedupe_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    seen: set[str] = set()
    unique: list[EvidenceItem] = []
    for item in items:
        item_id = item.id
        if item_id in seen:
            suffix = hashlib.sha1(json.dumps(item.model_dump(), sort_keys=True).encode("utf-8")).hexdigest()[:4]
            item = item.model_copy(update={"id": f"{item_id}-{suffix}"})
        seen.add(item.id)
        unique.append(item)
    return unique
