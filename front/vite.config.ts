import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite 配置：
// - strictPort: Tauri 期望前端固定监听 5173 端口，端口被占用时直接报错而不是切换端口
// - 这里通过环境变量 VITE_API_BASE_URL 让开发模式可以指向不同的后端地址
//   例如：VITE_API_BASE_URL=http://127.0.0.1:8001 npm run dev
export default defineConfig({
  plugins: [react()],
  // Tauri 默认会以相对路径加载打包后的前端，因此这里使用相对路径
  base: "./",
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    // 输出目录，Tauri 通过 tauri.conf.json 中的 frontendDist 字段指向这里
    outDir: "dist",
    emptyOutDir: true,
  },
});
