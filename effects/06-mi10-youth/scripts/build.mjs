import { cp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { transform } from 'esbuild';
import { entries, readEntry, root } from './project.mjs';

const output = path.join(root, 'dist');
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(path.join(root, 'public'), output, { recursive: true });
await mkdir(path.join(output, 'vendor'), { recursive: true });
await cp(path.join(root, 'node_modules/playcanvas/build/output/playcanvas.js'), path.join(output, 'vendor/playcanvas.js'));
await mkdir(path.join(output, 'scene'), { recursive: true });
await cp(path.join(root, 'src/scene/config.json'), path.join(output, 'scene/config.json'));
await cp(path.join(root, 'src/scene/scene.json'), path.join(output, 'scene/scene.json'));
for (const name of ['index.html', 'canvas.html']) {
  await cp(path.join(root, 'src', name), path.join(output, name));
}
await mkdir(path.join(output, 'runtime'), { recursive: true });
for (const name of Object.keys(entries)) {
  const source = await readEntry(name);
  const result = await transform(source, {
    loader: 'js',
    target: 'es2018',
    charset: 'utf8',
    minifyWhitespace: true,
    minifySyntax: false,
    minifyIdentifiers: false,
    sourcemap: 'external',
    sourcefile: `${name}.source.js`,
    legalComments: 'inline',
  });
  await writeFile(path.join(output, 'runtime', name), `${result.code}\n//# sourceMappingURL=${name}.map\n`);
  await writeFile(path.join(output, 'runtime', name + '.map'), result.map);
}
await mkdir(path.join(output, 'styles'), { recursive: true });
for (const name of await readdir(path.join(root, 'src/styles'))) {
  const source = await readFile(path.join(root, 'src/styles', name), 'utf8');
  const result = await transform(source, { loader: 'css', minifyWhitespace: true, minifySyntax: false });
  await writeFile(path.join(output, 'styles', name), result.code);
}
console.log(`Built ${Object.keys(entries).length} script entries and local assets into ${output}`);
