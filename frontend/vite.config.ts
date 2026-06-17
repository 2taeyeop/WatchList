import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발 시 /api 호출을 로컬 FastAPI(:8000)로 프록시 → CORS 없이 프론트는 항상 상대경로 /api 사용.
// 운영에선 nginx 가 동일하게 /api 를 백엔드로 보낸다(프론트 코드는 그대로).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
