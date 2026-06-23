# Knowledge Map 桌面版说明

本文档描述如何把 Knowledge Map 改造成 **Tauri + React + FastAPI sidecar** 的本地桌面应用。
原有 Web 开发模式继续保留，桌面版只是额外的一层壳。

---

## 1. 桌面版架构

```text
┌──────────────────────────────────────────────────────────────┐
│ 用户双击 Knowledge Map.exe                                    │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ Tauri 主进程（Rust） src-tauri/src/main.rs                    │
│  1. 通过 tauri::api::process::Command 拉起 sidecar           │
│  2. 把 %APPDATA%/Knowledge-Map 通过环境变量注入给后端        │
│  3. 按行扫描后端 stdout，拿到 KNOWLEDGE_MAP_LISTENING_ON url  │
│  4. 轮询 {url}/api/health，就绪后调用 window.eval 注入        │
│     window.__KNOWLEDGE_MAP_API_URL__                         │
│  5. 关闭窗口时 child.kill() 一起回收后端                     │
└──────────────────────────────────────────────────────────────┘
              │                                          │
              ▼                                          ▼
┌───────────────────────────────┐   ┌────────────────────────────────────┐
│ WebView（Tauri 内嵌）         │   │ sidecar exe（PyInstaller 单文件）  │
│  - 加载 front/dist            │   │  run_backend.py 打包而来            │
│  - React 读取                 │   │  - 自动选端口（8000~8003）          │
│    window.__KNOWLEDGE_MAP_    │   │  - 输出 stdout 协议行               │
│    API_URL__                  │   │  - 启动 uvicorn(src.main:app)       │
│  - fetch 调用本地 FastAPI     │◀──┤  - 不开 reload                      │
└───────────────────────────────┘   └────────────────────────────────────┘
                                                  │
                                                  ▼
                                    ┌─────────────────────────────┐
                                    │ FastAPI / LangGraph 后端    │
                                    │  src/main.py 中的所有接口    │
                                    │  Redis fallback → JSON 文件 │
                                    └─────────────────────────────┘
```

关键设计：

- **stdout 协议**：`KNOWLEDGE_MAP_LISTENING_ON <url>` / `KNOWLEDGE_MAP_READY` /
  `KNOWLEDGE_MAP_ERROR <msg>`，由 `desktop/backend/run_backend.py` 输出，由
  `src-tauri/src/main.rs` 解析。
- **动态端口**：默认 8000，被占用时自动尝试 8001、8002、8003。
- **数据目录重定向**：通过 `KNOWLEDGE_MAP_DATA_DIR` 把 papers.json / uploads / paper /
  runtime_kv.json / .env 全部写入 `%APPDATA%\Knowledge-Map`。
- **Redis 不强制依赖**：`src/database/redis_client.py` 在 Redis 不可用时降级到
  `runtime_kv.json`（在用户数据目录中）。

---

## 2. 开发环境要求

| 工具                | 版本             | 用途                           |
| ------------------- | ---------------- | ------------------------------ |
| Node.js             | ≥ 18             | 前端 / Tauri CLI              |
| Python              | ≥ 3.10           | 后端                          |
| Rust + Cargo        | ≥ 1.70           | Tauri 桌面壳                  |
| Tauri CLI           | ≥ 1.6（npm 安装）| 桌面打包                      |
| Windows SDK / WebView2 | 系统自带       | Tauri Windows 运行时          |
| Tesseract OCR       | 可选             | 仅扫描版 PDF 需要             |

Tauri 1.x Windows 还需要 Microsoft C++ Build Tools（安装 Rust 时通常会提示）。

---

## 3. Windows 开发启动步骤

### 3.1 一次性准备

```powershell
# 1. 安装 Rust（https://rustup.rs）
# 2. 安装 Node.js 18+
# 3. 安装 Python 3.10+

# 在项目根目录
cd D:\...\Knowledge-Map-App

# 前端依赖
cd front
npm install
cd ..

# 根目录依赖（提供 npm run tauri:* 脚本）
npm install

# Python 依赖
python -m pip install -r requirements.txt
```

### 3.2 模式 A：纯 Web 开发（保留原有模式）

```powershell
# 终端 1：后端
python desktop\backend\run_backend.py

# 终端 2：前端
cd front
npm run dev
# 访问 http://localhost:5173
```

> 此模式下不依赖 Tauri，前端通过 `import.meta.env.VITE_API_BASE_URL`
> 或 `window.__KNOWLEDGE_MAP_API_URL__` 解析后端地址，兜底 `http://127.0.0.1:8000`。

### 3.3 模式 B：Tauri 桌面开发

```powershell
# 准备 sidecar 二进制（首次或后端代码变更后执行）
powershell -ExecutionPolicy Bypass -File desktop\backend\build_backend.ps1

# 启动 Tauri（会自动调起 Vite dev server）
npm run tauri:dev
```

Tauri dev 模式下：

- 前端走 `http://localhost:5173`（Vite dev server，由 `beforeDevCommand` 拉起）。
- Tauri 主进程会启动 sidecar，sidecar 监听本地端口。
- API 地址通过 `window.__KNOWLEDGE_MAP_API_URL__` 注入到前端。

### 3.4 模式 C：开发时只跑后端 + 真前端构建

适用于想验证 `front/dist` 在 Tauri 中的加载效果。

```powershell
npm run build:front
npm run tauri:dev
```

---

## 4. 后端 sidecar 打包步骤

```powershell
# 在项目根目录执行
powershell -ExecutionPolicy Bypass -File desktop\backend\build_backend.ps1
```

产物：`src-tauri/binaries/knowledge-map-backend-x86_64-pc-windows-msvc.exe`

脚本内部做了：

1. `pip install -r requirements.txt`
2. `pip install pyinstaller`
3. `pyinstaller --onefile --name knowledge-map-backend-x86_64-pc-windows-msvc ...`
4. 把打包后的 exe 复制到 `src-tauri/binaries/`

如果你的依赖在打包时报 "ModuleNotFoundError"，可以通过环境变量追加 hidden import：

```powershell
$env:PYINSTALLER_HIDDEN_IMPORTS = "langchain_core,some_other_module"
powershell -ExecutionPolicy Bypass -File desktop\backend\build_backend.ps1
```

---

## 5. Tauri 打包步骤

```powershell
# 1. 先打好后端 sidecar（见第 4 节）
# 2. 再打桌面安装包
npm run tauri:build
```

产物在 `src-tauri/target/release/bundle/`：

- `msi/Knowledge Map_0.1.0_x64_en-US.msi`（MSI 安装包）
- `nsis/Knowledge Map_0.1.0_x64-setup.exe`（NSIS 安装包）

发布时建议先用虚拟机或干净系统验证一次安装流程。

---

## 6. Redis 降级说明

| 模式        | REDIS_URL              | 行为                                                |
| ----------- | ---------------------- | --------------------------------------------------- |
| 开发模式    | `redis://localhost:6379/0` | 尝试连接 Redis；连不上自动 fallback 到 JSON 文件 |
| 桌面模式    | 空                     | 直接使用 JSON 文件，不尝试连 Redis                  |

降级时 KV 数据写入：

```
开发：src/data/runtime_kv.json
桌面：%APPDATA%\Knowledge-Map\runtime_kv.json
```

如果用户既想用桌面版又想用 Redis（例如多任务并行），可手动在
`%APPDATA%\Knowledge-Map\.env` 中设置 `REDIS_URL=redis://127.0.0.1:6379/0`，
重启 App 即可。

---

## 7. 数据存储目录说明

### 开发模式

```
Knowledge-Map-App/
├── src/data/papers.json         # 论文集合
├── src/data/analysis/           # 单篇分析结果
├── src/data/runtime_kv.json     # KV fallback
├── uploads/                     # 上传暂存
└── paper/                       # PDF 永久存放
```

### 桌面模式

```
%APPDATA%\Knowledge-Map\
├── papers.json
├── analysis/
├── runtime_kv.json
├── uploads/
├── paper/
└── .env                         # 通过设置页写入的 API Key 等
```

如何切换：通过环境变量 `KNOWLEDGE_MAP_DATA_DIR` 即可。
Tauri 主进程会自动在启动时把该变量设置为用户数据目录并传给后端。

---

## 8. 常见问题

### Q1：8000 端口被占用怎么办？

后端会自动尝试 8001、8002、8003。实际监听端口会通过
`KNOWLEDGE_MAP_LISTENING_ON <url>` 协议行告诉 Tauri，前端会拿到正确的地址。

如果你需要强制端口：

```powershell
$env:KNOWLEDGE_MAP_PORT = "9000"
python desktop\backend\run_backend.py
```

### Q2：PyInstaller 打包失败 / 打出来的 exe 运行报 ModuleNotFoundError？

- 先按报错模块名追加 `PYINSTALLER_HIDDEN_IMPORTS`。
- `langgraph`、`pydantic`、`fastapi`、`uvicorn` 经常需要 `--collect-submodules`，脚本已经默认带上。
- 仍然失败时改成 `--onedir` 临时打包，看完整的 import 错误信息后再回 `--onefile`。
- 排查建议：先在干净虚拟环境里 `pip install -r requirements.txt` 然后再打包，避免开发机器残留的包路径干扰。

### Q3：没装 Tesseract OCR 能用吗？

可以。`OCR_ENABLED=false` 时不会走 Tesseract；桌面模式下默认仅依赖
PyMuPDF / pypdf 的纯文本提取，足以处理大部分非扫描版 PDF。

如果用户开启 `OCR_ENABLED=true` 但没装 Tesseract，后端会在解析 PDF 时
抛出明确错误信息提示安装。

### Q4：MinerU 没装能用吗？

可以。后端按 `PDF_PARSER_BACKEND=auto` 的优先级降级：
`MinerU → PyMuPDF → pypdf`。MinerU CLI 不可用时直接 fallback。

### Q5：API Key 配置失败 / 前端无法连接后端？

按顺序排查：

1. **后端有没有起？** 看 Tauri 控制台输出，应能看到
   `[backend] KNOWLEDGE_MAP_LISTENING_ON http://127.0.0.1:8000`。
2. **健康检查通过了吗？** 看到 `[tauri] backend ready at ...` 表示通过了。
3. **window 注入了吗？** 在 DevTools Console 输入
   `window.__KNOWLEDGE_MAP_API_URL__`，应当返回后端地址。
4. **CORS？** 后端 CORS 已经放行 `tauri://localhost` 和 `http://tauri.localhost`。

### Q6：Windows 安装包运行后窗口白屏？

- 检查 `front/dist/index.html` 是否存在；运行 `npm run build:front` 后重新打包。
- 检查 Tauri 日志（在 `%APPDATA%\<bundle-id>` 或运行目录下）。
- 临时把 `windows_subsystem` 改为 `console` 重打包，让 stderr 直接显示。

### Q7：关闭 App 后端口还在被占用？

理论上 `CommandChild::kill` 会清理子进程。如果你看到残留：

- 用 `Get-Process knowledge-map-backend* | Stop-Process -Force` 强杀。
- 在任务管理器中按名称筛选。
- 反馈 issue，附上 sidecar 的 stdout 日志。

### Q8：打包后 App 启动很慢？

PyInstaller `--onefile` 模式每次启动都要解压。优化方向：

- 换成 `--onedir`（更大但更快），相应 Tauri 配置改 `externalBin` 指向目录。
- 或在 SSD 上跑（机械硬盘 onefile 解压明显慢）。

---

## 9. 进一步优化方向（未完成）

- **首屏 loading 窗口**：当前后端还在启动时主窗口已经显示，可以加一个
  独立 loading 窗口（或 splashscreen）等就绪再切主窗。
- **后端日志面板**：把 stdout 通过 IPC 推给前端，做调试面板。
- **自动下载 Tesseract**：首次启动检测到 OCR 需求时引导用户安装。
- **多语言**：当前 UI 文案仍为中文。
