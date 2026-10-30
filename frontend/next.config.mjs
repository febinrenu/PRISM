/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output → tiny Docker runtime image (Module F).
  output: "standalone",
  webpack: (config) => {
    // Required for react-pdf (canvas is not available in SSR)
    config.resolve.alias.canvas = false;
    return config;
  },
  // Baseline headers for every page. (A Content-Security-Policy needs a nonce for Next's inline
  // scripts and is not set here.)
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
