# Knowledge Map 打包专用干净环境脚本（Windows / PowerShell）
#
# 目的：
#   sidecar exe 体积过大，根因是在臃肿的全局 Python 环境里跑 PyInstaller，
#   导致一堆与运行无关的库（numpy / pandas / matplotlib / pytest ...）被一起打包。
#   本脚本在项目下建一个「只装 requirements.txt + pyinstaller」的干净虚拟环境，
#   之后用这个环境的 python 去打包，体积能显著下降。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts/setup_clean_env.ps1
#
# 打包时让 build_backend.ps1 用这个环境（二选一）：
#   1) 先激活：.venv-build\Scripts\Activate.ps1，再跑 build_backend.ps1
#   2) 直接指定：设置环境变量 BUILD_PYTHON 指向 .venv-build\Scripts\python.exe
#      （需要 build_backend.ps1 已支持 BUILD_PYTHON；当前脚本会优先读它）
#
# 可选环境变量：
#   VENV_NAME   虚拟环境目录名，默认 .venv-build
#   PY_VER      指定 python 版本可执行文件，默认沿用 PATH 里的 python

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path        # scripts
$projectRoot = Split-Path -Parent $scriptRoot                         # 项目根
Set-Location $projectRoot
Write-Host "setup >> project root: $projectRoot" -ForegroundColor Cyan

# ---------- 1. 定位 Python ----------
$python = if ($env:PY_VER) { $env:PY_VER } else { (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $python) {
    $python = (Get-Command py -ErrorAction SilentlyContinue).Source
    if ($python) { $python = "$python -3.12" }  # py 启动器需带版本参数
}
if (-not $python) {
    throw "未找到 Python（python / py）。请先安装 Python 3.11+。"
}
Write-Host "setup >> python: $python"

# ---------- 2. 创建虚拟环境 ----------
$venvName = if ($env:VENV_NAME) { $env:VENV_NAME } else { ".venv-build" }
$venvDir = Join-Path $projectRoot $venvName
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (Test-Path $venvPython) {
    Write-Host "setup >> 已存在虚拟环境 $venvName，将复用（如需重建请先删除该目录）" -ForegroundColor Yellow
} else {
    Write-Host "setup >> 创建虚拟环境 $venvName ..." -ForegroundColor Cyan
    & $python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw "创建虚拟环境失败" }
}

# ---------- 3. 在干净环境内只装必需依赖 ----------
Write-Host "setup >> 升级 pip ..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip | Out-Null

Write-Host "setup >> 安装 requirements.txt + pyinstaller（仅这些）..." -ForegroundColor Cyan
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "安装 requirements.txt 失败" }
& $venvPython -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "安装 pyinstaller 失败" }

# ---------- 4. 打印已装包清单（用于核对没有多余库）----------
Write-Host ""
Write-Host "setup >> 干净环境已装包清单：" -ForegroundColor Green
& $venvPython -m pip list --format=columns

Write-Host ""
Write-Host "setup >> 完成。接下来用这个环境打包：" -ForegroundColor Green
Write-Host "    `$env:BUILD_PYTHON = `"$venvPython`"" -ForegroundColor White
Write-Host "    powershell -ExecutionPolicy Bypass -File desktop\backend\build_backend.ps1" -ForegroundColor White
Write-Host "（或先激活：$venvDir\Scripts\Activate.ps1，再直接跑 build_backend.ps1）" -ForegroundColor White
