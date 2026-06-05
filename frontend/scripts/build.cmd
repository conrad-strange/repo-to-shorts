@echo off
setlocal
set "ROOT_DIR=%~dp0..\.."
set "FRONTEND_DIR=%~dp0.."
call :resolve_node

"%NODE_EXE%" "%FRONTEND_DIR%\node_modules\typescript\lib\tsc.js" --noEmit -p "%FRONTEND_DIR%\tsconfig.json"
if errorlevel 1 exit /b %errorlevel%

"%NODE_EXE%" "%FRONTEND_DIR%\node_modules\typescript\lib\tsc.js" --noEmit -p "%FRONTEND_DIR%\tsconfig.node.json"
if errorlevel 1 exit /b %errorlevel%

"%NODE_EXE%" "%FRONTEND_DIR%\node_modules\vite\bin\vite.js" build
exit /b %errorlevel%

:resolve_node
if defined NODE_EXE if exist "%NODE_EXE%" exit /b 0
if exist "%ROOT_DIR%\.env" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT_DIR%\.env") do (
    if /I "%%A"=="NODE_EXE" set "ENV_NODE_EXE=%%B"
  )
)
if defined ENV_NODE_EXE if exist "%ENV_NODE_EXE%" (
  set "NODE_EXE=%ENV_NODE_EXE%"
  exit /b 0
)
for /f "delims=" %%F in ('dir /b /s "%ROOT_DIR%\.tools\node-*-win-x64\node.exe" 2^>nul') do (
  if not defined NODE_EXE set "NODE_EXE=%%F"
)
if defined NODE_EXE if exist "%NODE_EXE%" exit /b 0
for %%F in (node.exe) do set "NODE_EXE=%%~$PATH:F"
if defined NODE_EXE exit /b 0
echo Node.js was not found. Install Node.js 20.19+ or run scripts\install-portable-tools.ps1.
exit /b 1
