/**
 * 全局类型声明：
 * - 让 TypeScript 识别 window.__KNOWLEDGE_MAP_API_URL__（Tauri 桌面模式运行时注入的 API 地址）
 * - 让 TypeScript 识别 import.meta.env.VITE_API_BASE_URL
 */

export {};

declare global {
  interface Window {
    __KNOWLEDGE_MAP_API_URL__?: string;
  }
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
