$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$toolsDir = Join-Path $projectRoot ".tools"
$downloadsDir = Join-Path $toolsDir "downloads"

New-Item -ItemType Directory -Force -Path $downloadsDir | Out-Null

Write-Host "Resolving latest Node.js LTS Windows x64 zip..."
$nodeIndex = Invoke-RestMethod -Uri "https://nodejs.org/dist/index.json"
$nodeRelease = $nodeIndex |
  Where-Object { $_.lts -and ($_.files -contains "win-x64-zip") } |
  Select-Object -First 1

if (-not $nodeRelease) {
  throw "Could not find a Node.js LTS release with win-x64 zip."
}

$nodeVersion = $nodeRelease.version
$nodeZipName = "node-$nodeVersion-win-x64.zip"
$nodeUrl = "https://nodejs.org/dist/$nodeVersion/$nodeZipName"
$nodeZipPath = Join-Path $downloadsDir $nodeZipName
$nodeExtractDir = Join-Path $toolsDir "node-$nodeVersion-win-x64"

if (-not (Test-Path $nodeZipPath)) {
  Write-Host "Downloading $nodeUrl"
  Invoke-WebRequest -Uri $nodeUrl -OutFile $nodeZipPath
}

if (-not (Test-Path $nodeExtractDir)) {
  Expand-Archive -LiteralPath $nodeZipPath -DestinationPath $toolsDir -Force
}

$ffmpegZipName = "ffmpeg-release-essentials.zip"
$ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/$ffmpegZipName"
$ffmpegZipPath = Join-Path $downloadsDir $ffmpegZipName

if (-not (Test-Path $ffmpegZipPath)) {
  Write-Host "Downloading $ffmpegUrl"
  Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZipPath
}

Expand-Archive -LiteralPath $ffmpegZipPath -DestinationPath $toolsDir -Force

$nodeExe = Get-ChildItem -Path $toolsDir -Recurse -Filter "node.exe" |
  Where-Object { $_.FullName -like "*node-*-win-x64*" } |
  Select-Object -First 1
$npmCmd = Get-ChildItem -Path $toolsDir -Recurse -Filter "npm.cmd" |
  Where-Object { $_.FullName -like "*node-*-win-x64*" } |
  Select-Object -First 1
$ffmpegExe = Get-ChildItem -Path $toolsDir -Recurse -Filter "ffmpeg.exe" |
  Select-Object -First 1

if (-not $nodeExe -or -not $npmCmd -or -not $ffmpegExe) {
  throw "Install finished, but one or more tool executables were not found."
}

$toolEnvPath = Join-Path $toolsDir "tool-paths.env"
@(
  "NODE_EXE=$($nodeExe.FullName)"
  "NPM_CMD=$($npmCmd.FullName)"
  "FFMPEG_EXE=$($ffmpegExe.FullName)"
) | Set-Content -Path $toolEnvPath -Encoding UTF8

Write-Host ""
Write-Host "Portable tools installed."
Write-Host "Node:   $($nodeExe.FullName)"
Write-Host "npm:    $($npmCmd.FullName)"
Write-Host "FFmpeg: $($ffmpegExe.FullName)"
Write-Host ""
Write-Host "Tool env written to: $toolEnvPath"
Write-Host "Copy these values into .env if you want the app to use explicit paths."
