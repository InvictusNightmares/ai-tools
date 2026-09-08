import { readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const manifest = JSON.parse(await readFile(path.join(root, 'asset-manifest.json'), 'utf8'));
const known = new Set(manifest.map(asset => asset.path));
let bytes = 0;
for (const asset of manifest) {
  const content = await readFile(path.join(root, 'public', asset.path));
  if (content.length !== asset.bytes || createHash('sha256').update(content).digest('hex') !== asset.sha256) {
    throw new Error(`Asset content changed: ${asset.path}`);
  }
  bytes += content.length;
}
async function scan(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) { if (entry.name !== 'engine') await scan(file); continue; }
    if (!/\.(?:js|jsx)$/.test(entry.name)) continue;
    const source = await readFile(file, 'utf8');
    if (/gamemcu|cuer_zhao|shujupie|alicdn|Logo-container/i.test(source)) {
      throw new Error(`Unexpected author or analytics reference: ${file}`);
    }
    for (const [, literal] of source.matchAll(/["'](res\/[^"'\n]+\.(?:png|jpg|webp|glb|bin|hdr|mp3))["']/g)) {
      let local = literal.replace('res/', '1.0.5/');
      if (!local.includes('.raw')) local = local.replace(/\.(png|jpe?g)$/, '.webp').replace(/\.glb$/, '.bin');
      if (!known.has(local)) throw new Error(`Missing local asset: ${local}`);
    }
  }
}
await scan(path.join(root, 'src'));
console.log(`Verified ${manifest.length} local assets, ${bytes.toLocaleString()} bytes; hashes and source references passed.`);
