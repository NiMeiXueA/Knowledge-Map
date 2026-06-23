/**
 * 统一的 API baseURL 解析逻辑。
 *
 * 解析优先级：
 * 1. Vite 构建期环境变量 VITE_API_BASE_URL（开发模式常用）
 * 2. 运行时注入的全局变量 window.__KNOWLEDGE_MAP_API_URL__（Tauri 桌面模式注入）
 * 3. 兜底值 http://127.0.0.1:8000
 *
 * 桌面模式下，Tauri 会在加载页面之前向后端发起健康检查，
 * 拿到实际监听端口后，通过全局变量的方式注入到前端，
 * 这样无论后端最终监听的是 8000 / 8001 / 8002，前端都能正确访问。
 *
 * window 自定义字段的类型声明见 front/src/global.d.ts。
 */

export function resolveApiBaseUrl(): string {
  const fromVite = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (fromVite && fromVite.trim().length > 0) {
    return fromVite.replace(/\/+$/, "");
  }
  if (typeof window !== "undefined" && window.__KNOWLEDGE_MAP_API_URL__) {
    return window.__KNOWLEDGE_MAP_API_URL__.replace(/\/+$/, "");
  }
  return "http://127.0.0.1:8000";
}

export const API_BASE_URL = resolveApiBaseUrl();
