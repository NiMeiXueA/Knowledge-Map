# Knowledge Map 后端 sidecar 打包脚本（Windows / PowerShell）
#
# 目标：
#   使用 PyInstaller 把 desktop/backend/run_backend.py 打包成单文件 exe，
#   输出到 src-tauri/binaries/knowledge-map-backend-x86_64-pc-windows-msvc.exe，
#   供 Tauri sidecar 加载。
#
# 使用方式：
#   powershell -ExecutionPolicy Bypass -File desktop/backend/build_backend.ps1
#
# 可选环境变量：
#   PYINSTALLER_HIDDEN_IMPORTS  额外追加 hidden import（逗号分隔）
#   TARGET_TRIPLE               默认 x86_64-pc-windows-msvc，可覆盖

$ErrorActionPreference = "Stop"

# ---------- 1. 工作目录定位 ----------
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path      # desktop/backend
$projectRoot = Split-Path -Parent (Split-Path -Parent $scriptRoot) # 项目根
Set-Location $projectRoot
Write-Host "build >> project root: $projectRoot" -ForegroundColor Cyan

# ---------- 2. 依赖与产物目录 ----------
$binariesDir = Join-Path $projectRoot "src-tauri\binaries"
if (-not (Test-Path $binariesDir)) {
    New-Item -ItemType Directory -Force -Path $binariesDir | Out-Null
}

# ---------- 3. Python & PyInstaller ----------
# 优先用 BUILD_PYTHON 指定的解释器（指向 setup_clean_env.ps1 建的干净 venv，体积最小）；
# 否则回退到 PATH 里的 python / py。
$python = $env:BUILD_PYTHON
if (-not $python) {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $python) {
    $python = (Get-Command py -ErrorAction SilentlyContinue).Source
}
if (-not $python) {
    throw "未找到 Python 可执行文件（python / py）。请确保 Python 已安装并加入 PATH。"
}
Write-Host "build >> python: $python"
if (-not $env:BUILD_PYTHON) {
    Write-Host "build >> 提示：未设置 BUILD_PYTHON，正在用全局 Python。为减小体积建议先用 scripts/setup_clean_env.ps1 建干净 venv，再 `$env:BUILD_PYTHON=...\python.exe" -ForegroundColor Yellow
}

# 干净 venv 已含依赖；全局环境下才需要联网装依赖，避免在 CI 之外被全局环境污染
if (-not $env:BUILD_PYTHON) {
    & $python -m pip install --upgrade pip | Out-Null
    & $python -m pip install -r requirements.txt | Out-Null
    & $python -m pip install pyinstaller | Out-Null
} else {
    # 干净环境里 pyinstaller 可能缺（用户只装了 requirements），补装一次
    & $python -m pip install pyinstaller --quiet | Out-Null
}

# ---------- 4. 目标文件名（Tauri sidecar 命名约定） ----------
$targetTriple = if ($env:TARGET_TRIPLE) { $env:TARGET_TRIPLE } else { "x86_64-pc-windows-msvc" }
$outputName = "knowledge-map-backend-$targetTriple"
$distDir = Join-Path $projectRoot "dist_pyinstaller"
$workDir = Join-Path $projectRoot "build_pyinstaller"

# 清理上次产物
if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }
if (Test-Path $workDir) { Remove-Item -Recurse -Force $workDir }

# ---------- 5. 隐式依赖（PyInstaller 无法静态分析） ----------
# 这些是 LangGraph / pydantic / PyMuPDF / pytesseract 等常见容易漏掉的模块
# 注意：不要加 PIL._tkinter_finder——那是给 GUI 的 ImageTk 用的，会白白拉入 tkinter。
$hiddenImports = @(
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "pydantic",
    "pydantic._internal._core_utils",
    "email.mime.multipart",
    "email.mime.text",
    "langgraph",
    "langgraph.graph",
    "langgraph.errors",
    "fitz",
    "pymupdf",
    "pypdf",
    "PIL",
    "pytesseract",
    "redis",
    "redis.connection",
    "httpx",
    "dotenv",
    "multipart",
    "python_multipart"
)
if ($env:PYINSTALLER_HIDDEN_IMPORTS) {
    $hiddenImports += $env:PYINSTALLER_HIDDEN_IMPORTS.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}
$hiddenImports = @($hiddenImports | Select-Object -Unique)
$hiddenArgs = @()
foreach ($mod in $hiddenImports) {
    $hiddenArgs += "--hidden-import"
    $hiddenArgs += $mod
}

# ---------- 5.1 显式排除（减小体积） ----------
# 这些模块后端运行时绝不会用到，但脏环境里可能被 PyInstaller 误判并打包进来。
# 若未来真的引入了某个依赖（例如用 matplotlib 画图），记得从下面移除对应项。
$excludeModules = @(
    "tkinter",
    "_tkinter",
    "PIL._tkinter_finder",
    "pytest",
    "_pytest",
    "sphinx",
    "IPython",
    "notebook",
    "jupyter",
    "matplotlib"
)
if ($env:PYINSTALLER_EXCLUDE_MODULES) {
    $excludeModules += $env:PYINSTALLER_EXCLUDE_MODULES.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}
$excludeModules = @($excludeModules | Select-Object -Unique)
$excludeArgs = @()
foreach ($mod in $excludeModules) {
    $excludeArgs += "--exclude-module"
    $excludeArgs += $mod
}

# ---------- 6. 调用 PyInstaller ----------
$entry = Join-Path $projectRoot "desktop\backend\run_backend.py"

# add-data：src 包含所有后端源码；.env.example 仅作示例，桌面模式 .env 落在用户目录
$addDataArgs = @(
    "--add-data", "src;src",
    "--add-data", ".env.example;.",
    "--add-data", "requirements.txt;."
)

# 收集子模块：pydantic / fastapi / uvicorn / langgraph 经常需要
$collectArgs = @(
    "--collect-submodules", "langgraph",
    "--collect-submodules", "pydantic",
    "--collect-submodules", "fastapi",
    "--collect-submodules", "uvicorn",
    "--collect-submodules", "redis",
    "--collect-data", "pydantic"
)

$pyinstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--name", $outputName,
    "--paths", ".",
    "--workpath", $workDir,
    "--distpath", $distDir
) + $addDataArgs + $hiddenArgs + $excludeArgs + $collectArgs + @($entry)

Write-Host "build >> running PyInstaller..." -ForegroundColor Cyan
& $python -m PyInstaller @pyinstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 打包失败（exit $LASTEXITCODE）"
}

# ---------- 7. 拷贝到 src-tauri/binaries ----------
$builtExe = Join-Path $distDir "$outputName.exe"
if (-not (Test-Path $builtExe)) {
    throw "未找到打包产物：$builtExe"
}

$targetExe = Join-Path $binariesDir "$outputName.exe"
Copy-Item -Force $builtExe $targetExe
Write-Host "build >> copied -> $targetExe" -ForegroundColor Green
Write-Host "build >> done. Tauri sidecar will pick up $outputName.exe" -ForegroundColor Green
