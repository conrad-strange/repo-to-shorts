from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pathspec

from gva.models.repo import FileRole, RepoFile

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".cache",
    "target",
}

BINARY_SUFFIXES = {
    ".7z",
    ".bin",
    ".bmp",
    ".db",
    ".dll",
    ".doc",
    ".docx",
    ".exe",
    ".gif",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lockb",
    ".mov",
    ".mp3",
    ".mp4",
    ".onnx",
    ".pdf",
    ".png",
    ".pyc",
    ".pyd",
    ".rar",
    ".so",
    ".sqlite",
    ".tar",
    ".wav",
    ".webp",
    ".zip",
}

CONFIG_NAMES = {
    ".env.example",
    "compose.yaml",
    "docker-compose.yml",
    "dockerfile",
    "go.mod",
    "package.json",
    "pnpm-workspace.yaml",
    "poetry.lock",
    "pyproject.toml",
    "requirements.txt",
    "tsconfig.json",
    "vite.config.ts",
    "webpack.config.js",
}

ENTRY_NAMES = {
    "app.py",
    "cli.py",
    "index.js",
    "index.ts",
    "main.go",
    "main.py",
    "main.ts",
    "server.js",
    "server.ts",
}

LANGUAGE_BY_SUFFIX = {
    ".css": "CSS",
    ".go": "Go",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".md": "Markdown",
    ".py": "Python",
    ".rs": "Rust",
    ".sh": "Shell",
    ".tsx": "TypeScript",
    ".ts": "TypeScript",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
}


@dataclass(frozen=True)
class ScanOptions:
    max_files: int = 80
    max_file_bytes: int = 300_000
    excerpt_chars: int = 6_000
    tree_max_entries: int = 160
    tree_max_depth: int = 3


def scan_project(path: Path, options: ScanOptions | None = None) -> list[RepoFile]:
    options = options or ScanOptions()
    root = path.resolve()
    gitignore_spec = _load_gitignore(root)

    candidates: list[Path] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(root)
        if _should_skip(relative, gitignore_spec):
            continue
        if file_path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            size = file_path.stat().st_size
        except OSError:
            continue
        if size > options.max_file_bytes:
            continue
        candidates.append(file_path)

    candidates.sort(key=lambda item: _file_priority(item.relative_to(root)))
    selected = candidates[: options.max_files]

    return [
        RepoFile(
            path=_to_posix(file_path.relative_to(root)),
            language=_detect_language(file_path),
            role=_detect_role(file_path.relative_to(root)),
            excerpt=_read_excerpt(file_path, options.excerpt_chars),
            size=file_path.stat().st_size,
        )
        for file_path in selected
    ]


def build_tree_overview(path: Path, options: ScanOptions | None = None) -> str:
    options = options or ScanOptions()
    root = path.resolve()
    gitignore_spec = _load_gitignore(root)
    lines: list[str] = []

    def visit(directory: Path, depth: int) -> None:
        if len(lines) >= options.tree_max_entries or depth > options.tree_max_depth:
            return
        try:
            children = sorted(directory.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        except OSError:
            return

        for child in children:
            if len(lines) >= options.tree_max_entries:
                return
            relative = child.relative_to(root)
            if _should_skip(relative, gitignore_spec):
                continue
            if child.is_file() and child.suffix.lower() in BINARY_SUFFIXES:
                continue
            marker = "/" if child.is_dir() else ""
            indent = "  " * depth
            lines.append(f"{indent}{child.name}{marker}")
            if child.is_dir():
                visit(child, depth + 1)

    visit(root, 0)
    if len(lines) >= options.tree_max_entries:
        lines.append("...")
    return "\n".join(lines)


def detect_stack(files: list[RepoFile]) -> list[str]:
    paths = {file.path.lower() for file in files}
    names = {Path(path).name for path in paths}
    suffixes = {Path(file.path).suffix.lower() for file in files}
    stack: list[str] = []

    if "package.json" in names:
        stack.append("Node.js")
    if "pyproject.toml" in names or "requirements.txt" in names:
        stack.append("Python")
    if "go.mod" in names:
        stack.append("Go")
    if "dockerfile" in names:
        stack.append("Docker")
    if ".tsx" in suffixes or ".ts" in suffixes:
        stack.append("TypeScript")
    if ".jsx" in suffixes or ".js" in suffixes:
        stack.append("JavaScript")
    if any(path.endswith("vite.config.ts") or path.endswith("vite.config.js") for path in paths):
        stack.append("Vite")
    if any(path.endswith("remotion.config.ts") for path in paths):
        stack.append("Remotion")

    return list(dict.fromkeys(stack))


def _load_gitignore(root: Path) -> pathspec.PathSpec | None:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return None
    try:
        patterns = gitignore.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        patterns = gitignore.read_text(errors="ignore").splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def _should_skip(relative: Path, gitignore_spec: pathspec.PathSpec | None) -> bool:
    parts = set(relative.parts)
    if parts & EXCLUDED_DIRS:
        return True
    normalized = _to_posix(relative)
    if gitignore_spec and gitignore_spec.match_file(normalized):
        return True
    return False


def _file_priority(relative: Path) -> tuple[int, int, str]:
    role = _detect_role(relative)
    role_order = {
        "readme": 0,
        "config": 1,
        "entry": 2,
        "source": 3,
        "doc": 4,
        "test": 5,
        "other": 6,
    }
    return (role_order[role], len(relative.parts), _to_posix(relative).lower())


def _detect_role(relative: Path) -> FileRole:
    name = relative.name.lower()
    suffix = relative.suffix.lower()
    parts = {part.lower() for part in relative.parts}

    if name.startswith("readme"):
        return "readme"
    if name in CONFIG_NAMES or suffix in {".toml", ".yaml", ".yml", ".json"}:
        return "config"
    if name in ENTRY_NAMES:
        return "entry"
    if "test" in parts or "tests" in parts or name.startswith("test_") or name.endswith(".test.ts"):
        return "test"
    if suffix in {".md", ".rst"} or "docs" in parts:
        return "doc"
    if suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java"}:
        return "source"
    return "other"


def _detect_language(path: Path) -> str | None:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower())


def _read_excerpt(path: Path, max_chars: int) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    text = text.replace("\r\n", "\n")
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n..."


def _to_posix(path: Path) -> str:
    return path.as_posix()
