import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

export const root = fileURLToPath(new URL('../', import.meta.url));
export const entries = JSON.parse(await readFile(new URL('./entries.json', import.meta.url), 'utf8'));

// The original scene scripts share PlayCanvas constructors and globals.
// Keep their registration order and classic-script scope in both dev and build.
export async function readEntry(name) {
  if (!Object.hasOwn(entries, name)) throw new Error(`Unknown entry: ${name}`);
  const sources = await Promise.all(entries[name].map(async file =>
    `// Source: ${file}\n${await readFile(path.join(root, file), 'utf8')}\n`
  ));
  return sources.join('\n;\n');
}
