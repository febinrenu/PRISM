// Exit 0 when the production build is missing or older than any source file,
// 1 when it is current. Used by start.bat to skip `next build` when it can.
import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const stamp = join(root, ".next", "BUILD_ID");
if (!existsSync(stamp)) process.exit(0);
const built = statSync(stamp).mtimeMs;

const inputs = ["src", "public", "package-lock.json", "next.config.mjs", "next.config.js",
  "tailwind.config.ts", "postcss.config.mjs", "postcss.config.js", "tsconfig.json", ".env.local", ".env.production"];

function newer(p) {
  if (!existsSync(p)) return false;
  const s = statSync(p);
  if (!s.isDirectory()) return s.mtimeMs > built;
  return readdirSync(p).some((f) => newer(join(p, f)));
}

process.exit(inputs.some((f) => newer(join(root, f))) ? 0 : 1);
