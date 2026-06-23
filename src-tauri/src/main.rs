#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use std::env;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex, mpsc};
use std::time::{Duration, Instant};

use tauri::{Manager, WindowEvent};

const LISTENING_TAG: &str = "KNOWLEDGE_MAP_LISTENING_ON";
const ERROR_TAG: &str = "KNOWLEDGE_MAP_ERROR";
const BACKEND_READY_TIMEOUT_SECS: u64 = 90;

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
    let sidecar_name = format!("{}-{}{}", name, target_triple, ext);

    // In dev mode (cargo tauri dev), look in target/debug/
    if let Ok(manifest_dir) = env::var("CARGO_MANIFEST_DIR") {
        let dev_path = PathBuf::from(&manifest_dir)
            .parent()
            .unwrap()
            .join("target")
            .join("debug")
            .join(&sidecar_name);
        if dev_path.exists() {
            return dev_path;
        }
    }

    // In release mode, look next to the current exe
    if let Ok(exe) = env::current_exe() {
        if let Some(dir) = exe.parent() {
            let release_path = dir.join(&sidecar_name);
            if release_path.exists() {
                return release_path;
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

            let sidecar_path = resolve_sidecar("knowledge-map-backend");
            eprintln!("[tauri] launching sidecar: {:?}", sidecar_path);

            let mut cmd = Command::new(&sidecar_path);
            cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
            for (k, v) in &sidecar_env {
                cmd.env(k, v);
            }

            let mut child = cmd.spawn().expect("failed to spawn backend sidecar");
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
                for event in rx {
                    match event {
                        SidecarEvent::Stdout(line) => {
                            let trimmed = line.trim();
                            if trimmed.is_empty() {
                                continue;
                            }
                            eprintln!("[backend] {}", trimmed);
                            if let Some(url) = trimmed.strip_prefix(LISTENING_TAG) {
                                let url = url.trim();
                                if heard_listening.is_none() {
                                    heard_listening = Some(url.to_string());
                                    if let Ok(mut slot) = base_url_arc.lock() {
                                        *slot = Some(url.to_string());
                                    }
                                    let url_for_health = url.to_string();
                                    let win_clone = window_for_ready.clone();
                                    let base_arc = base_url_arc.clone();
                                    std::thread::spawn(move || {
                                        let ok = wait_for_health(
                                            &url_for_health,
                                            Duration::from_secs(BACKEND_READY_TIMEOUT_SECS),
                                        );
                                        if ok {
                                            inject_api_url(&win_clone, &url_for_health);
                                            if let Ok(mut slot) = base_arc.lock() {
                                                *slot = Some(url_for_health.clone());
                                            }
                                            eprintln!(
                                                "[tauri] backend ready at {}",
                                                url_for_health
                                            );
                                        } else {
                                            eprintln!(
                                                "[tauri] backend health check timed out at {}",
                                                url_for_health
                                            );
                                            let msg = format!(
                                                "后端在 {} 秒内未就绪，请检查日志或重启应用。",
                                                BACKEND_READY_TIMEOUT_SECS
                                            );
                                            inject_error_banner(&win_clone, &msg);
                                        }
                                    });
                                }
                            } else if let Some(msg) = trimmed.strip_prefix(ERROR_TAG) {
                                eprintln!("[backend error] {}", msg.trim());
                            }
                        }
                        SidecarEvent::Stderr(line) => {
                            eprint!("[backend stderr] {}", line);
                        }
                    }
                }
            });

            // sidecar 还在启动期间，先在页面上显示"正在连接后端"提示；
            // 健康检查通过后 inject_api_url 会自动移除该 banner。
            // 不再注入兜底 url——sidecar 实际端口可能是 8001/8002/8003，
            // 兜底到 8000 会让前端在启动窗口期打到错误地址。
            inject_connecting_banner(&window);

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
