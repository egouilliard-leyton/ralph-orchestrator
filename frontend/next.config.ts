import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

const nextConfig: NextConfig = {
  // Output as static export for serving from FastAPI (production only)
  output: isDev ? undefined : "export",

  // Output directory for the static build (production only)
  // In dev mode, we use the default .next directory
  ...(isDev ? {} : { distDir: "../ralph_orchestrator/server/static" }),

  // Disable image optimization for static export
  images: {
    unoptimized: true,
  },

  // Trailing slash for cleaner static file serving
  trailingSlash: true,

  // Set the turbopack root to this directory to fix module resolution
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
