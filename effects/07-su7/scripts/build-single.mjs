import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";

const root = fileURLToPath(new URL("../", import.meta.url));
const manifest = JSON.parse(await readFile(path.join(root, "asset-manifest.json"), "utf8"));
const mimeTypes = {
  ".mp3": "audio/mpeg",
  ".webp": "image/webp",
  ".jpg": "image/jpeg",
  ".glb": "model/gltf-binary",
  ".bin": "application/octet-stream",
  ".hdr": "application/octet-stream",
};
const assets = Object.fromEntries(await Promise.all(manifest.map(async (asset) => {
  const type = mimeTypes[path.extname(asset.path)];
  if (!type) throw new Error(`Unknown embedded asset type: ${asset.path}`);
  const data = await readFile(path.join(root, "public", asset.path));
  return [asset.path, { type, base64: data.toString("base64") }];
})));

// Build one classic script so file:// works without module imports or CORS.
const result = await build({
  root,
  publicDir: false,
  build: {
    write: false,
    sourcemap: false,
    cssCodeSplit: false,
    modulePreload: false,
    rollupOptions: {
      input: path.join(root, "src/main.jsx"),
      output: { format: "iife", inlineDynamicImports: true },
    },
  },
});
if (Array.isArray(result) || !result.output) throw new Error("Expected one build output.");
const scripts = result.output.filter((item) => item.type === "chunk");
const styles = result.output.filter((item) => item.type === "asset" && item.fileName.endsWith(".css"));
const other = result.output.filter((item) => item.type === "asset" && !item.fileName.endsWith(".css"));
if (scripts.length !== 1 || other.length || scripts[0].imports.length || scripts[0].dynamicImports.length) {
  throw new Error("Standalone build unexpectedly emitted external dependencies.");
}

const template = await readFile(path.join(root, "index.html"), "utf8");
const css = styles.map((item) => String(item.source)).join("\n").replace(/<\/style/gi, "<\\/style");
const js = scripts[0].code.replace(/<\/script/gi, "<\\/script");
const payload = JSON.stringify(assets).replace(/</g, "\\u003c");
const html = template
  .replace("</head>", `<style>${css}</style></head>`)
  .replace(/<script\s+type="module"\s+src="\.\/src\/main\.jsx"><\/script>/,
    () => `<script id="su7-embedded-assets" type="application/json">${payload}</script>\n<script>${js}</script>`);
if (html === template || /<script\b[^>]*\bsrc\s*=/i.test(html)) {
  throw new Error("Failed to inline the application entry.");
}

const output = path.join(root, "dist-single", "su7.html");
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, html);
console.log(`\nStandalone HTML: ${output}`);
console.log(`${manifest.length} embedded assets; ${Buffer.byteLength(html).toLocaleString()} bytes. No server required.`);
