from __future__ import annotations

import re
from collections.abc import Iterable


GENERIC_VISIBLE_TEXT = {
    "文字",
    "画面",
    "镜头",
    "动画",
    "转场",
    "卡片",
    "标签",
    "表情",
    "第一步",
    "第二步",
    "第三步",
}

DIRECTION_REPLACEMENTS = {
    "开发者烦恼表情": "开发者痛点",
    "镜头聚焦GitHub仓库": "GitHub 仓库",
    "镜头聚焦 GitHub 仓库": "GitHub 仓库",
    "克隆仓库动画": "克隆仓库",
    "视频输出动画": "视频输出",
    "技术标签展示": "技术标签",
    "文件列表展示": "文件列表",
}

DIRECTION_TOKENS = (
    "文字弹出",
    "镜头聚焦",
    "镜头",
    "动画",
    "转场",
    "弹出",
    "淡入",
    "淡出",
    "滑入",
    "滑出",
    "出现",
    "展示",
    "显示",
    "高亮",
    "特写",
    "扫过",
    "聚焦",
    "表情",
)

GITHUB_REPO_URL_RE = re.compile(
    r"(?:https?://)?github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?(?:[/?#][^\s，。！？!?；;、]*)?",
    flags=re.IGNORECASE,
)

TECH_PHRASE_RULES: tuple[tuple[str, str], ...] = (
    (r"Repo\s*to\s*Shorts", "Repo to Shorts"),
    (r"输入[^，。；;!?！？]{0,8}(URL|url)", "输入 URL"),
    (r"(自动\s*)?[Cc]lone|克隆", "自动 Clone"),
    (r"扫描[^，。；;!?！？]{0,12}(README|Readme|readme|配置|代码)", "扫描 README/代码"),
    (r"证据索引", "证据索引"),
    (r"(LLM|大语言模型)", "LLM 脚本"),
    (r"Verifier|校验", "Verifier 校验"),
    (r"Edge\s*TTS|TTS", "Edge TTS"),
    (r"字幕", "字幕"),
    (r"Remotion", "Remotion 渲染"),
    (r"Web\s*UI|本地\s*Web", "Web UI"),
    (r"DeepSeek", "DeepSeek"),
    (r"9:16", "9:16 竖屏"),
    (r"Python", "Python"),
    (r"TypeScript", "TypeScript"),
    (r"FastAPI", "FastAPI"),
    (r"GitHub", "GitHub"),
    (r"README|Readme|readme", "README"),
)

SPOKEN_PREFIXES = (
    "这个工具叫",
    "你只需要",
    "它就会",
    "然后",
    "最后",
    "比如",
    "有了",
    "生成的视频不是最终稿",
    "项目提供了",
)

SPOKEN_SENTENCE_MARKERS = (
    "这个工具",
    "你只需要",
    "它就会",
    "有了",
    "找不到",
    "后台调用",
    "可以看到",
    "比如",
    "然后",
    "最后",
    "其实",
    "所以",
    "生成的视频不是最终稿",
    "项目提供了",
    "一条命令即可",
    "它来自",
)


def clean_visible_text(value: object, limit: int | None = None) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    text = compact_github_repo_references(_normalize_terms(clean_text_value(value)))
    if not text:
        return None

    for old, new in DIRECTION_REPLACEMENTS.items():
        text = text.replace(old, new)

    original = text
    for token in DIRECTION_TOKENS:
        text = text.replace(token, "")

    text = re.sub(r"\s+", " ", text).strip(" ，,、：:;-")
    text = _normalize_terms(text)
    if not text:
        return None
    if text in GENERIC_VISIBLE_TEXT:
        return None
    if len(text) <= 2 and any(token in original for token in DIRECTION_TOKENS):
        return None
    if limit is not None:
        text = text[:limit]
    return text


def clean_visible_text_list(values: Iterable[object], limit: int | None = None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_visible_text(value, limit=limit)
        if not text:
            continue
        key = normalize_visible_key(text)
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def clean_text_value(text: object) -> str:
    if text is None or isinstance(text, (dict, list)):
        return ""
    cleaned = re.sub(r"\s+", " ", str(text).replace("\r", " ")).strip()
    cleaned = re.sub(r"[*_`#>\[\]{}<>|\\^]+", "", cleaned)
    return cleaned.strip(" -")


def compact_github_repo_handle(value: object) -> str | None:
    text = clean_text_value(value)
    if not text:
        return None
    match = GITHUB_REPO_URL_RE.search(text)
    if match:
        candidate = match.group(0)
    elif re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", text):
        candidate = text
    else:
        return None
    candidate = re.sub(r"^https?://", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"^github\.com/", "", candidate, flags=re.IGNORECASE)
    parts = [part for part in re.split(r"[/?#]+", candidate.strip("/")) if part]
    if len(parts) < 2:
        return None
    owner = parts[0]
    repo = parts[1]
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    return f"{owner}/{repo}"


def compact_github_repo_references(text: object) -> str:
    value = clean_text_value(text)
    if not value:
        return ""

    def replace(match: re.Match[str]) -> str:
        return compact_github_repo_handle(match.group(0)) or match.group(0)

    return GITHUB_REPO_URL_RE.sub(replace, value)


def normalize_visible_key(text: object) -> str:
    return re.sub(r"[\W_]+", "", clean_text_value(text).lower(), flags=re.UNICODE)


def dedupe_visible_texts(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = clean_text_value(value)
        if not text:
            continue
        key = normalize_visible_key(text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def looks_like_spoken_sentence(text: str | None) -> bool:
    value = clean_text_value(text)
    if not value:
        return False
    if any(marker in value for marker in SPOKEN_SENTENCE_MARKERS):
        return True
    if len(value) > 20 and re.search(r"[。！？!?；;]", value):
        return True
    if len(value) > 24 and re.search(r"[，,]", value):
        return True
    return False


def compact_visible_phrase(text: str | None) -> str | None:
    phrases = compact_visible_phrases(text)
    return phrases[0] if phrases else None


def compact_visible_phrases(text: str | None) -> list[str]:
    value = compact_github_repo_references(text)
    if not value:
        return []

    phrases: list[str] = []
    for pattern, label in TECH_PHRASE_RULES:
        if re.search(pattern, value, flags=re.IGNORECASE):
            phrases.append(label)

    for clause in re.split(r"[，。！？!?；;]+", value):
        candidate = clean_visible_text(_strip_spoken_prefixes(clause))
        if not candidate or looks_like_spoken_sentence(candidate):
            continue
        if len(candidate) <= 18 and not re.search(r"[。！？!?；;]", candidate):
            phrases.append(candidate)
    return dedupe_visible_texts(phrases)


def text_repeats_narration(text: str | None, narration: str | None) -> bool:
    cleaned = normalize_visible_key(text)
    spoken = normalize_visible_key(narration)
    if not cleaned or not spoken:
        return False
    if len(cleaned) >= 14 and cleaned in spoken:
        return True
    if len(cleaned) >= 18 and _longest_common_substring(cleaned, spoken) >= 14:
        return True
    return False


def _normalize_terms(text: str) -> str:
    return text.replace("READNE", "README").replace("Readne", "README").replace("readne", "README")


def _strip_spoken_prefixes(text: str) -> str:
    stripped = clean_text_value(text)
    changed = True
    while changed:
        changed = False
        for prefix in SPOKEN_PREFIXES:
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix) :].strip(" ，,、：:;-")
                changed = True
    return stripped


def _longest_common_substring(left: str, right: str) -> int:
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    best = 0
    for char_left in left:
        current = [0]
        for index, char_right in enumerate(right, start=1):
            value = previous[index - 1] + 1 if char_left == char_right else 0
            current.append(value)
            if value > best:
                best = value
        previous = current
    return best
