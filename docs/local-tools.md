# Local Tools

Node.js and FFmpeg should stay outside conda on Windows to avoid DLL conflicts.

Run this from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-portable-tools.ps1
```

The script installs portable tools under `.tools/` and writes discovered paths to:

```text
.tools/tool-paths.env
```

Copy the generated values into `.env`:

```env
NODE_EXE=...
NPM_CMD=...
FFMPEG_EXE=...
```

This keeps the project reproducible without modifying the global system PATH.
