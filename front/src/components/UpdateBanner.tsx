import { useEffect, useState } from "react";

type Status = "idle" | "available" | "downloading" | "installed" | "error";

type UpdateInfo = {
  version: string;
  body?: string;
};

export function UpdateBanner() {
  const [status, setStatus] = useState<Status>("idle");
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!("__TAURI_INTERNALS__" in window)) return;

    let cancelled = false;
    (async () => {
      try {
        const updater = await import("@tauri-apps/api/updater");
        const result = await updater.check();
        if (cancelled) return;
        if (result) {
          setUpdate({ version: result.version, body: result.body });
          setStatus("available");
        }
      } catch (err) {
        if (cancelled) return;
        console.warn("[update] check failed:", err);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "idle" || dismissed) return null;

  const doUpdate = async () => {
    if (!update) return;
    setStatus("downloading");
    try {
      const updater = await import("@tauri-apps/api/updater");
      const result = await updater.check();
      if (!result) {
        setStatus("error");
        setErrorMsg("更新信息已失效，请重启应用后再试");
        return;
      }
      await result.downloadAndInstall();
      setStatus("installed");
      const proc = await import("@tauri-apps/api/process");
      await proc.relaunch();
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : String(err));
    }
  };

  const message =
    status === "available"
      ? `发现新版本 v${update?.version}，是否立即更新？`
      : status === "downloading"
      ? "正在下载并安装更新，请稍候…"
      : status === "installed"
      ? "更新完成，正在重启…"
      : `更新失败：${errorMsg}`;

  const bg =
    status === "error" ? "#dc2626" : status === "installed" ? "#16a34a" : "#2563eb";

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        background: bg,
        color: "#fff",
        padding: "12px 16px",
        zIndex: 100000,
        fontFamily: "system-ui, -apple-system, sans-serif",
        fontSize: 14,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
      }}
    >
      <span>{message}</span>
      {status === "available" && (
        <>
          <button
            onClick={doUpdate}
            style={{
              background: "#fff",
              color: "#2563eb",
              border: "none",
              borderRadius: 4,
              padding: "4px 12px",
              fontWeight: 600,
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            立即更新
          </button>
          <button
            onClick={() => setDismissed(true)}
            style={{
              background: "transparent",
              color: "#fff",
              border: "1px solid rgba(255,255,255,0.5)",
              borderRadius: 4,
              padding: "4px 12px",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            稍后
          </button>
        </>
      )}
      {status === "error" && (
        <button
          onClick={() => setDismissed(true)}
          style={{
            background: "transparent",
            color: "#fff",
            border: "1px solid rgba(255,255,255,0.5)",
            borderRadius: 4,
            padding: "4px 12px",
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          关闭
        </button>
      )}
    </div>
  );
}
