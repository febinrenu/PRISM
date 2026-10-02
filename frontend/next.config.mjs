/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output → tiny Docker runtime image (Module F).
  output: "standalone",
  webpack: (config) => {
    // Required for react-pdf (canvas is not available in SSR)
    config.resolve.alias.canvas = false;
    return config;
  },
};

export default nextConfig;
