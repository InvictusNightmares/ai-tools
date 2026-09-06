import http from 'node:http';
import { createReadStream } from 'node:fs';
import { stat, realpath } from 'node:fs/promises';
import path from 'node:path';
import { entries, readEntry, root } from './project.mjs';

const preview = process.argv.includes('--preview');
const portFlag = process.argv.indexOf('--port');
const port = Number(portFlag === -1 ? process.env.PORT || (preview ? 8767 : 8766) : process.argv[portFlag + 1]);
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid port');
const mime = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.map': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif',
  '.mp4': 'video/mp4', '.ttf': 'font/ttf', '.dds': 'application/octet-stream',
};

function resolveRequest(urlPath) {
  if (preview) return { base: path.join(root, 'dist'), relative: urlPath === '/' ? 'index.html' : urlPath.slice(1) };
  if (urlPath === '/vendor/playcanvas.js') return { base: path.join(root, 'node_modules/playcanvas/build/output'), relative: 'playcanvas.js' };
  if (urlPath === '/' || urlPath === '/index.html') return { base: path.join(root, 'src'), relative: 'index.html' };
  if (urlPath === '/canvas.html') return { base: path.join(root, 'src'), relative: 'canvas.html' };
  if (/^\/styles\/[\w-]+\.css$/.test(urlPath) || /^\/scene\/(config|scene)\.json$/.test(urlPath)) {
    return { base: path.join(root, 'src'), relative: urlPath.slice(1) };
  }
  return { base: path.join(root, 'public'), relative: urlPath.slice(1) };
}

const server = http.createServer(async (req, res) => {
  try {
    if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
    const urlPath = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    res.setHeader('Cache-Control', 'no-store');
    if (!preview && urlPath.startsWith('/runtime/')) {
      const name = urlPath.slice('/runtime/'.length);
      if (!Object.hasOwn(entries, name)) { res.writeHead(404); res.end('Not found'); return; }
      const code = await readEntry(name);
      res.writeHead(200, { 'Content-Type': mime['.js'], 'Content-Length': Buffer.byteLength(code) });
      res.end(req.method === 'HEAD' ? undefined : code);
      return;
    }
    const { base, relative } = resolveRequest(urlPath);
    const filename = path.resolve(base, relative);
    if (!filename.startsWith(base + path.sep) || relative.split('/').some(part => part.startsWith('.'))) {
      res.writeHead(403); res.end('Forbidden'); return;
    }
    const actual = await realpath(filename);
    if (!actual.startsWith(await realpath(base) + path.sep)) { res.writeHead(403); res.end('Forbidden'); return; }
    const info = await stat(actual);
    if (!info.isFile()) { res.writeHead(404); res.end('Not found'); return; }
    res.setHeader('Content-Type', mime[path.extname(actual)] || 'application/octet-stream');
    res.setHeader('Accept-Ranges', 'bytes');
    let start = 0, end = info.size - 1, status = 200;
    if (req.headers.range) {
      const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range);
      if (!range || (!range[1] && !range[2])) { res.writeHead(416); res.end(); return; }
      if (range[1]) { start = Number(range[1]); end = range[2] ? Math.min(Number(range[2]), end) : end; }
      else start = Math.max(0, info.size - Number(range[2]));
      if (start > end || start >= info.size) {
        res.writeHead(416, { 'Content-Range': `bytes */${info.size}` }); res.end(); return;
      }
      status = 206;
      res.setHeader('Content-Range', `bytes ${start}-${end}/${info.size}`);
    }
    res.writeHead(status, { 'Content-Length': Math.max(0, end - start + 1) });
    if (req.method === 'HEAD' || info.size === 0) { res.end(); return; }
    const stream = createReadStream(actual, { start, end });
    stream.on('error', () => res.destroy());
    stream.pipe(res);
  } catch (error) {
    const status = error.code === 'ENOENT' ? 404 : error instanceof URIError ? 400 : 500;
    console.error(`${status} ${req.url}: ${error.message}`);
    if (!res.headersSent) res.writeHead(status);
    res.end(http.STATUS_CODES[status]);
  }
});
server.listen(port, '127.0.0.1', () => {
  console.log(`${preview ? 'Build preview' : 'Editable source'}: http://127.0.0.1:${port}`);
  if (!preview) console.log('Edit src/ and refresh the browser. No build required in development.');
});
