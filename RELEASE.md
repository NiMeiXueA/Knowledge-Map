# Knowledge Map 发布操作指南

本文档说明如何从干净环境打包桌面应用，并把一个新版本发布到 GitHub Releases。

> 当前要发布的目标版本：**v0.2.0**（`src-tauri/tauri.conf.json` 的 `package.version` 已设为 `0.2.0`）。
> 经核查 GitHub 上只有 `v0.2.0` 这一个历史 release/tag（不存在 `v0.2.1`），需要先删除它再用新代码重新发布。

发布由 GitHub Actions（`.github/workflows/release.yml`）自动完成：**推送一个 `v*` 形式的 tag** 即触发「构建 sidecar → 构建 Tauri 安装包 → 发布 Release → 上传 `latest.json` 更新清单」全流程。本地一般不需要手动打包，除非要在本机验证。

---

## 一、前置：删除旧的 v0.2.0 release 与 tag

重新发布同一个版本号前，必须先删掉 GitHub 上已有的 `v0.2.0` release 和 tag，否则 tauri-action 会因为 release 已存在而报错。

### 方式 A：用 GitHub CLI（推荐）

```powershell
# 安装 gh（已装可跳过）
winget install --id GitHub.cli
gh auth login

# 删除旧 release（不会删 tag）
gh release delete v0.2.0 --yes

# 删除远程 tag
git push --delete origin v0.2.0

# 删除本地 tag
git tag -d v0.2.0
```

### 方式 B：网页操作

1. 打开仓库的 **Releases** 页面 → 找到 `v0.2.0` → **Delete** 删除该 release。
2. 打开 **Tags** 页面 → 找到 `v0.2.0` → 删除。
3. 本地同步：`git fetch --prune --tags` 和 `git tag -d v0.2.0`。

---

## 二、（可选）本地干净打包验证

CI 已经在干净的 `setup-python` 环境里打包，**通常不需要本地打包**。仅当要在本机验证体积/可运行性时执行。

### 1. 建干净虚拟环境（减小 sidecar 体积的关键）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_clean_env.ps1
```

脚本会在项目下创建 `.venv-build`，只装 `requirements.txt` + `pyinstaller`，并打印已装包清单供核对（不应出现 numpy/pandas/matplotlib 等无关库）。

### 2. 用干净环境打包 sidecar

```powershell
$env:BUILD_PYTHON = ".\.venv-build\Scripts\python.exe"
powershell -ExecutionPolicy Bypass -File desktop/backend/build_backend.ps1
```

产物：`src-tauri/binaries/knowledge-map-backend-x86_64-pc-windows-msvc.exe`。
对比体积：干净环境下应明显小于此前的 368MB。

### 3. 桌面打包（MSI / NSIS 安装包）

```powershell
npm install
npm run tauri:build
```

产物在 `src-tauri/target/release/bundle/`（需要重新编译 Rust，首次较慢）。

---

## 三、提交代码并触发发布

### 1. 提交所有改动

工作区当前包含本次修复（AI 缩写 / 纯引用关系图 / 引用准确性增强 / 版本号重置 / 依赖精简 / 文档）以及之前未提交的改动（清理示例论文数据等）。一起提交：

```powershell
git add -A
git commit -m "release v0.2.0: AI 缩写、纯引用关系图、引用准确性增强、依赖瘦身"
```

### 2. 打 tag 并推送（触发发布）

```powershell
git tag v0.2.0
git push origin main
git push origin v0.2.0
```

推送 `v0.2.0` tag 后，`.github/workflows/release.yml` 自动开始构建并发布。可在仓库 **Actions** 页面观察进度。

### 3. 验证发布

- Actions 跑通后，**Releases** 页面会出现 `Knowledge Map v0.2.0`，附带 `Knowledge-Map_0.2.0_x64-setup.exe` / `.msi` 以及 `latest.json`（自动更新清单）。
- `latest.json` 由 `tauri.conf.json` 的 `updater.endpoints` 指向，已安装旧版本的用户会收到升级提示。

---

## 四、后续发新版本

1. 改 `src-tauri/tauri.conf.json` 的 `package.version`（例如 `0.2.1`）。
2. 提交后打对应 tag：`git tag v0.2.1 && git push origin v0.2.1`。
3. CI 自动发布。无需手动删除旧 release（版本号递增即可）。

---

## 附：体积排查清单（exe 仍然过大时）

- 确认是用 `BUILD_PYTHON` 指向 `.venv-build` 打的包，而不是全局 Python。
- 看 `.venv-build` 的 `pip list`：是否有意外混入的重库？`requirements.txt` 是否新增了带重型传递依赖的包？
- `build_backend.ps1` 的 `excludeModules` 是否覆盖了该库？没有可临时追加：
  `$env:PYINSTALLER_EXCLUDE_MODULES = "numpy,pandas,scipy"` 后重新打包（确认运行时确实不 import 它们）。
- 打包后用 `pyinstaller` 的 `--onefile` 解包或查看 `build_pyinstaller/` 下的 `Analysis-00.toc` 排查体积来源（注意该目录已被 gitignore，每次打包会重建）。
