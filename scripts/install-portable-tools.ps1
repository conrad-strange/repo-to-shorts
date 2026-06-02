param(
  [switch]$NoEnvUpdate
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$toolsDir = Join-Path $projectRoot ".tools"
$downloadsDir = Join-Path $toolsDir "downloads"
$envExamplePath = Join-Path $projectRoot ".env.example"
$envPath = Join-Path $projectRoot ".env"

function Set-EnvValue {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Key,
    [Parameter(Mandatory = $true)][string]$Value
  )

  $lines = @()
  if (Test-Path $Path) {
    $lines = Get-Content -Path $Path -Encoding UTF8
  }

  $pattern = "^$([regex]::Escape($Key))="
  $found = $false
  $next = foreach ($line in $lines) {
    if ($line -match $pattern) {
      $found = $true
      "$Key=$Value"
    } else {
      $line
    }
  }
  if (-not $found) {
    $next += "$Key=$Value"
  }
  $next | Set-Content -Path $Path -Encoding UTF8
}

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
  Sort-Object FullName -Descending |
  Select-Object -First 1
$npmCmd = Get-ChildItem -Path $toolsDir -Recurse -Filter "npm.cmd" |
  Where-Object { $_.FullName -like "*node-*-win-x64*" } |
  Sort-Object FullName -Descending |
  Select-Object -First 1
$ffmpegExe = Get-ChildItem -Path $toolsDir -Recurse -Filter "ffmpeg.exe" |
  Sort-Object FullName -Descending |
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

if (-not $NoEnvUpdate) {
  if (-not (Test-Path $envPath)) {
    if (Test-Path $envExamplePath) {
      Copy-Item -LiteralPath $envExamplePath -Destination $envPath
    } else {
      New-Item -ItemType File -Path $envPath | Out-Null
    }
  }
  Set-EnvValue -Path $envPath -Key "NODE_EXE" -Value $nodeExe.FullName
  Set-EnvValue -Path $envPath -Key "NPM_CMD" -Value $npmCmd.FullName
  Set-EnvValue -Path $envPath -Key "FFMPEG_EXE" -Value $ffmpegExe.FullName
}

Write-Host ""
Write-Host "Portable tools installed."
Write-Host "Node:   $($nodeExe.FullName)"
Write-Host "npm:    $($npmCmd.FullName)"
Write-Host "FFmpeg: $($ffmpegExe.FullName)"
Write-Host ""
Write-Host "Tool env written to: $toolEnvPath"
if (-not $NoEnvUpdate) {
  Write-Host ".env updated with NODE_EXE, NPM_CMD, and FFMPEG_EXE."
}
