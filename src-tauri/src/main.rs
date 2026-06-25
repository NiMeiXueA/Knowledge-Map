#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use std::env;
use std::fs::OpenOptions;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex, mpsc};
use std::time::{Duration, Instant};

use tauri::{Manager, WindowEvent};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

// Windows Job Object：把 sidecar（含 PyInstaller onefile 的 Python 子进程）
// 绑定到 Tauri 主进程生命周期。Tauri 退出（含崩溃、强杀）时 Windows 内核
// 自动级联 kill job 内全部进程，根治 python.exe 孤儿问题。
// 比 Python 端 watchdog 更可靠：不依赖子进程协作，不依赖 ctypes 调用。
#[cfg(target_os = "windows")]
mod win_job {
    #![allow(non_camel_case_types, non_upper_case_globals)]
    use std::os::windows::io::AsRawHandle;
    use std::process::Child;

    type HANDLE = *mut std::ffi::c_void;
    type BOOL = i32;
    type DWORD = u32;
    type ULONG_PTR = usize;

    const JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: ULONG_PTR = 0x2000;
    const JobObjectExtendedLimitInformation: DWORD = 9;

    #[repr(C)]
    #[derive(Default)]
    struct IoCounters {
        _0: u64,
        _1: u64,
        _2: u64,
        _3: u64,
        _4: u64,
        _5: u64,
    }

    #[repr(C)]
    #[derive(Default)]
    struct JobObjectBasicLimitInformation {
        _per_process_user_time: i64,
        _per_job_user_time: i64,
        limit_flags: ULONG_PTR,
        _min_ws: usize,
        _max_ws: usize,
        _active_process_limit: u32,
        _affinity: ULONG_PTR,
        _priority_class: u32,
        _scheduling_class: u32,
    }

    #[repr(C)]
    #[derive(Default)]
    struct JobObjectExtendedLimitInformation {
        basic: JobObjectBasicLimitInformation,
        io: IoCounters,
        _process_memory_limit: usize,
        _job_memory_limit: usize,
        _peak_process_memory_used: usize,
        _peak_job_memory_used: usize,
    }

    extern "system" {
        fn CreateJobObjectW(lp_job_attributes: *mut std::ffi::c_void, lp_name: *const u16) -> HANDLE;
        fn SetInformationJobObject(
            h_job: HANDLE,
            info_class: DWORD,
            info: *mut std::ffi::c_void,
            info_len: DWORD,
        ) -> BOOL;
        fn AssignProcessToJobObject(h_job: HANDLE, h_process: HANDLE) -> BOOL;
        fn CloseHandle(h: HANDLE) -> BOOL;
    }

    /// 把 child 加入 KillOnJobClose 的 Job Object。
    ///
    /// job handle 故意 leak：生命周期等同于 Tauri 主进程。Tauri 进程退出
    /// （含崩溃、任务管理器强杀）时 Windows 自动关闭 handle，触发
    /// KillOnJobClose，job 内所有进程级联 kill。
    ///
    /// 必须在 child spawn 后立即调用：PyInstaller onefile 的 boot loader
    /// 会很快 fork Python 子进程，趁早把 boot loader 加入 job，后续 fork
    /// 出来的 Python 子进程会自动继承 job 归属（Windows 8+ 默认行为）。
    pub fn assign_to_kill_on_close_job(child: &Child) -> std::io::Result<()> {
        let job = unsafe { CreateJobObjectW(std::ptr::null_mut(), std::ptr::null()) };
        if job.is_null() {
            return Err(std::io::Error::last_os_error());
        }

        let mut info = JobObjectExtendedLimitInformation::default();
        info.basic.limit_flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let rc = unsafe {
            SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                &mut info as *mut _ as *mut std::ffi::c_void,
                std::mem::size_of::<JobObjectExtendedLimitInformation>() as DWORD,
            )
        };
        if rc == 0 {
            let err = std::io::Error::last_os_error();
            unsafe { CloseHandle(job) };
            return Err(err);
        }

        let proc_handle = child.as_raw_handle() as usize as HANDLE;
        let rc = unsafe { AssignProcessToJobObject(job, proc_handle) };
        if rc == 0 {
            let err = std::io::Error::last_os_error();
            unsafe { CloseHandle(job) };
            return Err(err);
        }

        // 故意 leak：raw pointer 没有 Drop，绑定到本地变量即可保持 handle 打开。
        // 函数返回后 job 变量超出作用域，但 raw pointer 不会被关闭。
        let _leaked = job;
        Ok(())
    }
}

const LISTENING_TAG: &str = "KNOWLEDGE_MAP_LISTENING_ON";
const ERROR_TAG: &str = "KNOWLEDGE_MAP_ERROR";
const BACKEND_READY_TIMEOUT_SECS: u64 = 90;

/// 诊断日志：所有关键事件 + sidecar stdout/stderr 都同步落到这里。
/// release 模式下 windows_subsystem="windows" 看不到 eprintln，
/// 没有 backend-debug.log 就完全黑盒。
fn log_path() -> Option<PathBuf> {
    user_data_dir().map(|d| d.join("backend-debug.log"))
}

fn log_line(msg: impl AsRef<str>) {
    let msg = msg.as_ref();
    let stamped = format!("[{}] {}", chrono_like_stamp(), msg);
    eprintln!("{}", stamped);
    if let Some(path) = log_path() {
        if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(&path) {
            let _ = writeln!(f, "{}", stamped);
        }
    }
}

fn chrono_like_stamp() -> String {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    let secs = now.as_secs();
    let millis = now.subsec_millis();
    let (h, m, s) = ((secs / 3600) % 24, (secs / 60) % 60, secs % 60);
    format!("{:02}:{:02}:{:02}.{:03}", h, m, s, millis)
}

#[derive(Clone, Default)]
struct BackendState {
    base_url: Arc<Mutex<Option<String>>>,
    child: Arc<Mutex<Option<Child>>>,
}

enum SidecarEvent {
    Stdout(String),
    Stderr(String),
}

fn user_data_dir() -> Option<PathBuf> {
    #[cfg(target_os = "windows")]
    {
        if let Some(appdata) = env::var_os("APPDATA") {
            return Some(PathBuf::from(appdata).join("Knowledge-Map"));
        }
    }
    #[cfg(target_os = "macos")]
    {
        if let Some(home) = env::var_os("HOME") {
            return Some(
                PathBuf::from(home)
                    .join("Library")
                    .join("Application Support")
                    .join("Knowledge-Map"),
            );
        }
    }
    #[cfg(target_os = "linux")]
    {
        if let Some(home) = env::var_os("HOME") {
            return Some(
                PathBuf::from(home)
                    .join(".local")
                    .join("share")
                    .join("Knowledge-Map"),
            );
        }
    }
    None
}

fn resolve_sidecar(name: &str) -> PathBuf {
    let target_triple = std::env::var("CARGO_CFG_TARGET_TRIPLE")
        .unwrap_or_else(|_| "x86_64-pc-windows-msvc".to_string());
    let ext = if cfg!(target_os = "windows") {
        ".exe"
    } else {
        ""
    };
    let sidecar_name_with_triple = format!("{}-{}{}", name, target_triple, ext);
    let sidecar_name_bare = format!("{}{}", name, ext);

    // In dev mode (cargo tauri dev), look in target/debug/
    if let Ok(manifest_dir) = env::var("CARGO_MANIFEST_DIR") {
        let dev_path = PathBuf::from(&manifest_dir)
            .parent()
            .unwrap()
            .join("target")
            .join("debug")
            .join(&sidecar_name_with_triple);
        if dev_path.exists() {
            return dev_path;
        }
    }

    // In release mode, look next to the current exe
    if let Ok(exe) = env::current_exe() {
        if let Some(dir) = exe.parent() {
            // NSIS/MSI installers strip the target triple from the sidecar name
            let release_path = dir.join(&sidecar_name_bare);
            if release_path.exists() {
                return release_path;
            }
            // Dev-built sidecar keeps the target triple suffix
            let release_path_triple = dir.join(&sidecar_name_with_triple);
            if release_path_triple.exists() {
                return release_path_triple;
            }
        }
    }

    // Fallback: try bare name (assume it's on PATH)
    PathBuf::from(name)
}

fn wait_for_health(base_url: &str, timeout: Duration) -> bool {
    let url = format!("{}/api/health", base_url.trim_end_matches('/'));
    let started = Instant::now();
    let client = match reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
    {
        Ok(c) => c,
        Err(_) => return false,
    };
    while started.elapsed() < timeout {
        if let Ok(resp) = client.get(&url).send() {
            if resp.status().is_success() {
                return true;
            }
        }
        std::thread::sleep(Duration::from_millis(300));
    }
    false
}

fn inject_api_url(window: &tauri::Window, api_url: &str) {
    let escaped = api_url.replace('\\', "\\\\").replace('\'', "\\'");
    let js = format!("window.__KNOWLEDGE_MAP_API_URL__ = '{}';", escaped);
    let _ = window.eval(&js);
    let js2 = format!(
        "try {{ localStorage.setItem('KNOWLEDGE_MAP_API_URL', '{}'); }} catch (e) {{}}",
        escaped
    );
    let _ = window.eval(&js2);
    // listening + 健康检查都通过后，移除"正在连接后端"提示
    let _ = window.eval(
        "(function() {\
            var d = document.getElementById('km-connecting');\
            if (d) d.remove();\
        })();",
    );
}

fn inject_connecting_banner(window: &tauri::Window) {
    let js = "(function() {\
        if (document.getElementById('km-connecting')) return;\
        var d = document.createElement('div');\
        d.id = 'km-connecting';\
        d.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#0f766e;color:#fff;padding:12px;z-index:99999;font-family:system-ui,sans-serif;font-size:14px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.2);';\
        d.textContent = '正在启动后端服务…';\
        var attach = function() { document.body.appendChild(d); };\
        if (document.body) { attach(); } else { document.addEventListener('DOMContentLoaded', attach); }\
    })();";
    let _ = window.eval(js);
}

fn inject_error_banner(window: &tauri::Window, message: &str) {
    let escaped = message
        .replace('\\', "\\\\")
        .replace('\'', "\\'")
        .replace('"', "\\\"");
    let js = format!(
        "(function() {{\
            if (document.getElementById('km-backend-error')) return;\
            var d = document.createElement('div');\
            d.id = 'km-backend-error';\
            d.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#dc2626;color:#fff;padding:16px;z-index:99999;font-family:system-ui,sans-serif;font-size:14px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.2);';\
            d.innerHTML = \"{escaped}\" + ' <a href=\"#\" onclick=\"location.reload()\" style=\"color:#fff;text-decoration:underline;margin-left:8px;font-weight:600;\">点此重试</a>';\
            var attach = function() {{ document.body.appendChild(d); }};\
            if (document.body) {{ attach(); }} else {{ document.addEventListener('DOMContentLoaded', attach); }}\
        }})();",
        escaped = escaped
    );
    let _ = window.eval(&js);
}

fn main() {
    tauri::Builder::default()
        .manage(BackendState::default())
        .setup(|app| {
            let mut sidecar_env: Vec<(String, String)> = Vec::new();
            if let Some(data_dir) = user_data_dir() {
                if let Err(e) = std::fs::create_dir_all(&data_dir) {
                    eprintln!("failed to create data dir {:?}: {}", data_dir, e);
                }
                sidecar_env.push((
                    "KNOWLEDGE_MAP_DATA_DIR".to_string(),
                    data_dir.to_string_lossy().into_owned(),
                ));
                sidecar_env.push((
                    "KNOWLEDGE_MAP_ENV_PATH".to_string(),
                    data_dir.join(".env").to_string_lossy().into_owned(),
                ));
            }
            sidecar_env.push(("KNOWLEDGE_MAP_DESKTOP".to_string(), "1".to_string()));
            // 显式注入 Tauri 自己的 pid，sidecar 的 watchdog 监控这个 pid
            // （os.getppid() 在 PyInstaller onefile 模式下拿到的是 boot loader pid，
            // 不是 Tauri pid，监控错了对象，孤儿进程问题就无法根治）
            sidecar_env.push((
                "KNOWLEDGE_MAP_PARENT_PID".to_string(),
                std::process::id().to_string(),
            ));

            let sidecar_path = resolve_sidecar("knowledge-map-backend");
            log_line(format!("[tauri] launching sidecar: {:?}", sidecar_path));
            log_line(format!(
                "[tauri] KNOWLEDGE_MAP_DATA_DIR={:?}",
                sidecar_env
                    .iter()
                    .find(|(k, _)| k == "KNOWLEDGE_MAP_DATA_DIR")
                    .map(|(_, v)| v.as_str())
                    .unwrap_or("(unset)")
            ));

            let mut cmd = Command::new(&sidecar_path);
            cmd.stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped());
            // 关键：Tauri 主进程是 windows_subsystem="windows"，没 console。
            // 如果不设 CREATE_NO_WINDOW，Windows 会给 sidecar（console 子系统）
            // 创建一个新 console，新 console 的 stdio 会接管 Rust 设的 pipe，
            // 导致 Rust 读不到任何 sidecar 输出。CREATE_NO_WINDOW 让 sidecar
            // 完全用 Rust pipe 作为 stdio，不创建新 console。
            #[cfg(target_os = "windows")]
            cmd.creation_flags(CREATE_NO_WINDOW);
            for (k, v) in &sidecar_env {
                cmd.env(k, v);
            }

            let child = match cmd.spawn() {
                Ok(c) => c,
                Err(e) => {
                    log_line(format!("[tauri] FATAL: failed to spawn sidecar: {}", e));
                    panic!("failed to spawn backend sidecar: {}", e);
                }
            };
            let child_pid = child.id();
            log_line(format!("[tauri] sidecar spawned, pid={}", child_pid));

            // 立即把 sidecar 加入 KillOnJobClose 的 Job Object。
            // PyInstaller onefile boot loader 会很快 fork Python 子进程，
            // 趁早 assign 才能让 Python 子进程也继承 job 归属。
            // 即使 Tauri 主进程异常退出（崩溃/强杀），Windows 内核也会
            // 自动级联 kill job 内全部进程，根治 python.exe 孤儿问题。
            #[cfg(target_os = "windows")]
            {
                match win_job::assign_to_kill_on_close_job(&child) {
                    Ok(()) => log_line("[tauri] sidecar assigned to kill-on-close job"),
                    Err(e) => log_line(format!(
                        "[tauri] WARN: failed to assign sidecar to job \
                         (orphan-process protection degraded, falling back to Python watchdog): {}",
                        e
                    )),
                }
            }

            let mut child = child;
            let child_stdout = child.stdout.take().expect("no stdout");
            let child_stderr = child.stderr.take().expect("no stderr");

            let state: tauri::State<BackendState> = app.state();
            {
                let mut guard = state.child.lock().unwrap();
                *guard = Some(child);
            }

            let window = app.get_window("main").expect("main window not found");

            let base_url_arc = state.base_url.clone();
            let window_for_ready = window.clone();

            let (tx, rx) = mpsc::channel::<SidecarEvent>();

            let tx_out = tx.clone();
            std::thread::spawn(move || {
                let reader = BufReader::new(child_stdout);
                for line in reader.lines().flatten() {
                    let _ = tx_out.send(SidecarEvent::Stdout(line));
                }
            });

            let tx_err = tx.clone();
            std::thread::spawn(move || {
                let reader = BufReader::new(child_stderr);
                for line in reader.lines().flatten() {
                    let _ = tx_err.send(SidecarEvent::Stderr(line));
                }
            });

            drop(tx);

            tauri::async_runtime::spawn(async move {
                let mut heard_listening: Option<String> = None;
                log_line("[tauri] stdout/stderr listener task started");
                for event in rx {
                    match event {
                        SidecarEvent::Stdout(line) => {
                            let trimmed = line.trim();
                            if trimmed.is_empty() {
                                continue;
                            }
                            log_line(format!("[backend stdout] {}", trimmed));
                            if let Some(url) = trimmed.strip_prefix(LISTENING_TAG) {
                                let url = url.trim();
                                log_line(format!("[tauri] received LISTENING_ON: {}", url));
                                if heard_listening.is_none() {
                                    heard_listening = Some(url.to_string());
                                    if let Ok(mut slot) = base_url_arc.lock() {
                                        *slot = Some(url.to_string());
                                    }
                                    let url_for_health = url.to_string();
                                    let win_clone = window_for_ready.clone();
                                    let base_arc = base_url_arc.clone();
                                    std::thread::spawn(move || {
                                        log_line(format!(
                                            "[tauri] starting health check at {}",
                                            url_for_health
                                        ));
                                        let ok = wait_for_health(
                                            &url_for_health,
                                            Duration::from_secs(BACKEND_READY_TIMEOUT_SECS),
                                        );
                                        if ok {
                                            log_line(format!(
                                                "[tauri] health check passed, injecting API url"
                                            ));
                                            inject_api_url(&win_clone, &url_for_health);
                                            if let Ok(mut slot) = base_arc.lock() {
                                                *slot = Some(url_for_health.clone());
                                            }
                                            log_line(format!(
                                                "[tauri] backend ready at {}",
                                                url_for_health
                                            ));
                                        } else {
                                            log_line(format!(
                                                "[tauri] health check timed out at {}",
                                                url_for_health
                                            ));
                                            let msg = format!(
                                                "后端在 {} 秒内未就绪，请检查日志或重启应用。",
                                                BACKEND_READY_TIMEOUT_SECS
                                            );
                                            inject_error_banner(&win_clone, &msg);
                                        }
                                    });
                                }
                            } else if let Some(msg) = trimmed.strip_prefix(ERROR_TAG) {
                                log_line(format!("[backend ERROR tag] {}", msg.trim()));
                            }
                        }
                        SidecarEvent::Stderr(line) => {
                            log_line(format!("[backend stderr] {}", line));
                        }
                    }
                }
                log_line("[tauri] stdout/stderr listener task ended (sidecar exited?)");
            });

            // sidecar 还在启动期间，先在页面上显示"正在连接后端"提示；
            // 健康检查通过后 inject_api_url 会自动移除该 banner。
            // 不再注入兜底 url——sidecar 实际端口可能是 8001/8002/8003，
            // 兜底到 8000 会让前端在启动窗口期打到错误地址。
            log_line("[tauri] injecting connecting banner");
            inject_connecting_banner(&window);
            log_line("[tauri] setup complete");

            Ok(())
        })
        .on_window_event(|event| match event.event() {
            WindowEvent::CloseRequested { .. } | WindowEvent::Destroyed => {
                let window = event.window();
                if let Some(state) = window.try_state::<BackendState>() {
                    if let Ok(mut guard) = state.child.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
            }
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
