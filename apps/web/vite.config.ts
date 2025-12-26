import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_ORIGIN || "http://127.0.0.1:3001";
  const minioTarget = env.VITE_MINIO_ORIGIN || "http://127.0.0.1:9000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/health": apiTarget,
        "/v1": apiTarget,
        "/__minio": {
          target: minioTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/__minio/, ""),
        },
      },
    },
  };
});
