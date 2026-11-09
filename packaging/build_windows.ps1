#Requires -Version 5.1
<#
.SYNOPSIS
  Build 社媒视频混剪 Windows portable folder (+ optional Inno Setup).
.NOTES
  Run from repo root on Windows x64:
    powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
  Optional: -SkipInno  to skip Setup.exe
#>
param(
  [switch]$SkipInno,
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Ensure-ChineseIsl {
  $dest = Join-Path $Root "packaging\ChineseSimplified.isl"
  if (Test-Path $dest) { return }
  $urls = @(
    "https://raw.githubusercontent.com/jrsoftware/issrc/main/Files/Languages/ChineseSimplified.isl",
    "https://raw.githubusercontent.com/kira-96/Inno-Setup-Chinese-Simplified-Translation/main/ChineseSimplified.isl"
  )
  foreach ($u in $urls) {
    try {
      Write-Host "Downloading ChineseSimplified.isl"
      Invoke-WebRequest -Uri $u -OutFile $dest -UseBasicParsing
      if ((Get-Item $dest).Length -gt 500) { return }
    } catch {
      Write-Warning $_
    }
    Remove-Item $dest -ErrorAction SilentlyContinue
  }
  Write-Warning "未下载到 ChineseSimplified.isl。安装包将只用英文语言；便携版不受影响。"
}

$VersionFile = Join-Path $Root "assets\version.json"
$ver = "0.3.5"
if (Test-Path $VersionFile) {
  try {
    $vj = Get-Content $VersionFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($vj.version) { $ver = [string]$vj.version }
  } catch {}
}
Write-Host "==> version $ver" -ForegroundColor Cyan

$ffmpeg = Join-Path $Root "assets\ffmpeg\ffmpeg.exe"
$ffprobe = Join-Path $Root "assets\ffmpeg\ffprobe.exe"
if (-not (Test-Path $ffmpeg) -or -not (Test-Path $ffprobe)) {
  Write-Error @"
缺少 Windows ffmpeg 静态包。
请下载 win64 静态构建，将 ffmpeg.exe 与 ffprobe.exe 放到:
  assets\ffmpeg\
参考: assets\ffmpeg\README_PLACE_FFMPEG_HERE.txt
或先跑 CI / 本机脚本里的下载步骤后再打包。
"@
  exit 2
}

Write-Host "==> pip install deps + pyinstaller" -ForegroundColor Cyan
& $Python -m pip install -U pip
& $Python -m pip install -r requirements.txt
& $Python -m pip install pyinstaller

Write-Host "==> fetch flet-windows.zip (offline desktop client)" -ForegroundColor Cyan
& $Python packaging\fetch_flet_desktop_client.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> PyInstaller packaging/remix.spec" -ForegroundColor Cyan
& $Python -m PyInstaller --noconfirm --clean packaging\remix.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> verify flet-desktop is packed (no pip path)" -ForegroundColor Cyan
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
& $Python packaging\verify_windows_dist.py --smoke
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$distDir = Join-Path $Root "dist\社媒视频混剪"
if (-not (Test-Path $distDir)) {
  Write-Error "PyInstaller 未产出 dist\社媒视频混剪"
  exit 3
}
Write-Host "==> portable OK: $distDir" -ForegroundColor Green

if ($SkipInno) {
  Write-Host "跳过 Inno Setup (-SkipInno)" -ForegroundColor Yellow
  exit 0
}

$iscc = $null
foreach ($c in @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)) {
  if (Test-Path $c) { $iscc = $c; break }
}
if (-not $iscc) {
  $cmd = Get-Command iscc -ErrorAction SilentlyContinue
  if ($cmd) { $iscc = $cmd.Source }
}

if (-not $iscc) {
  Write-Warning "未找到 ISCC.exe。便携目录已可用；安装 Inno Setup 6 后重跑可生成 Setup.exe。"
  Write-Host "choco install innosetup -y" -ForegroundColor Yellow
  exit 0
}

Ensure-ChineseIsl
Write-Host "==> Inno Setup: $iscc" -ForegroundColor Cyan
Push-Location (Join-Path $Root "packaging")
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $iscc .\remix_setup.iss
$innoCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
Pop-Location
if ($innoCode -ne 0) {
  Write-Warning "Inno Setup 失败（便携目录已可用，不阻断）。常见原因：语言文件或 ISCC 版本。"
  exit 0
}
Write-Host "==> Setup 产出见 deliver_win\" -ForegroundColor Green
