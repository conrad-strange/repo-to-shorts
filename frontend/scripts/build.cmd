@echo off
setlocal
set "ROOT_DIR=%~dp0..\.."
set "FRONTEND_DIR=%~dp0.."
set "NODE_EXE=%ROOT_DIR%\.tools\node-v24.16.0-win-x64\node.exe"

if not exist "%NODE_EXE%" (
  echo Portable Node not found: %NODE_EXE%
  exit /b 1
)

"%NODE_EXE%" "%FRONTEND_DIR%\node_modules\typescript\bin\tsc" -b
if errorlevel 1 exit /b %errorlevel%

"%NODE_EXE%" "%FRONTEND_DIR%\node_modules\vite\bin\vite.js" build
