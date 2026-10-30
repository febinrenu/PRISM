/** @type {import('next').NextConfig} */
const api = process.env.NEXT_PUBLIC_API_URL;
const apiOrigin = api === "same-origin" ? "" : api || "http://127.0.0.1:8000";
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigin}`.trim(),
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'self'",
].join("; ");

const nextConfig = {
  // Standalone output → tiny Docker runtime image (Module F).
  output: "standalone",
  webpack: (config) => {
    // Required for react-pdf (canvas is not available in SSR)
    config.resolve.alias.canvas = false;
    return config;
  },
  // Baseline headers for every page. Next's own inline bootstrap scripts need 'unsafe-inline' for
  // scripts (a nonce would make every page dynamic), so the policy restricts where anything may load
  // from and what may embed the app, which is what stops a script from elsewhere or a framing attack.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
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
