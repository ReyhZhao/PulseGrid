/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// In dev, API calls are proxied to a locally running control plane so the
// SPA and Django share an origin (required for session cookies).
const backend = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // Hand-written service worker (src/sw.ts) so we control the push and
      // notification-click handlers; the plugin injects the precache manifest.
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      registerType: "autoUpdate",
      injectRegister: false,
      manifest: {
        name: "PulseGrid",
        short_name: "PulseGrid",
        description: "Multi-region uptime and TLS monitoring",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#020617",
        theme_color: "#0f172a",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/icons/icon-maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      // Serve the service worker in `npm run dev` too, so push can be tested
      // without a production build.
      devOptions: { enabled: true, type: "module" },
    }),
  ],
  server: {
    proxy: Object.fromEntries(
      ["/api", "/_allauth", "/accounts", "/admin", "/django-static"].map((path) => [
        path,
        { target: backend, changeOrigin: false },
      ]),
    ),
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
