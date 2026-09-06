import { mkdir, writeFile } from 'node:fs/promises';
import { CDP } from './cdp.mjs';
import { detectorResult } from './completion.mjs';

const targets = [
  ['net-coffee-claude', 'https://ip.net.coffee/claude/'],
  ['fuck-claude', 'https://fuck-claude.vercel.app/'],
];
const mode = process.argv[2] ?? 'run';
if (!['run', 'inspect'].includes(mode)) throw new Error('Usage: site-check [run|inspect]');
const token = process.env.BROWSERLESS_TOKEN ?? '';
if (!/^[a-f0-9]{64}$/.test(token)) throw new Error('Browser credential unavailable');
if (process.env.BROWSERLESS_BASE_URL !== 'ws://headless-chrome:3000/chrome') throw new Error('Unexpected browser endpoint');
if (process.env.BROWSERLESS_PROXY_SERVER !== 'http://172.18.0.1:7898') throw new Error('Unexpected configured proxy');
const endpoint = new URL(process.env.BROWSERLESS_BASE_URL);
endpoint.searchParams.set('token', token);
endpoint.searchParams.set('--proxy-server', process.env.BROWSERLESS_PROXY_SERVER);
endpoint.searchParams.set('--lang', process.env.BROWSERLESS_LANGUAGE || 'en-US');
const safeError = error => String(error?.message ?? error).replaceAll(token, '[REDACTED]').slice(0, 1500);
const publicUrl = value => { try { const u = new URL(value); return (u.origin + u.pathname).slice(0, 300); } catch { return '[invalid URL]'; } };
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const runId = new Date().toISOString().replaceAll(':', '-');
const output = `/output/${runId}`;
await mkdir(output, { recursive: true, mode: 0o750 });
const report = { runId, mode, execution: 'Agentbox Chrome via configured 7898 proxy',
  emulation: 'Native CDP; no timezone, locale, user-agent, font, viewport or WebRTC overrides', results: [] };
let cdp;
try {
  cdp = await CDP.connect(endpoint.toString());
  report.browser = await cdp.call('Browser.getVersion');
  for (const [name, url] of targets) {
    const result = { name, url, startedAt: new Date().toISOString(), failures: [], responses: [], completed: false };
    report.results.push(result);
    const { targetId } = await cdp.call('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await cdp.call('Target.attachToTarget', { targetId, flatten: true });
    const call = (method, params = {}) => cdp.call(method, params, sessionId);
    const evaluate = async expression => {
      const reply = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
      if (reply.exceptionDetails) throw new Error('Page evaluation failed');
      return reply.result.value;
    };
    const requests = new Map();
    let mainFrameId;
    const onEvent = message => {
      if (message.sessionId !== sessionId) return;
      const p = message.params;
      if (message.method === 'Network.requestWillBeSent' && requests.size < 500) requests.set(p.requestId, publicUrl(p.request.url));
      if (message.method === 'Network.loadingFailed' && result.failures.length < 60)
        result.failures.push({ url: requests.get(p.requestId), error: p.errorText });
      if (message.method === 'Network.responseReceived') {
        if (p.type === 'Document' && p.frameId === mainFrameId) result.httpStatus = p.response.status;
        if (['Fetch', 'XHR'].includes(p.type) && result.responses.length < 100)
          result.responses.push({ url: publicUrl(p.response.url), status: p.response.status });
      }
    };
    cdp.listeners.add(onEvent);
    try {
      await call('Page.enable'); await call('Runtime.enable'); await call('Network.enable');
      mainFrameId = (await call('Page.getFrameTree')).frameTree.frame.id;
      const navigation = await call('Page.navigate', { url });
      if (navigation.errorText) throw new Error(navigation.errorText);
      for (let i = 0; i < 40; i++) {
        if (await evaluate(`Boolean(location.origin === ${JSON.stringify(new URL(url).origin)} && document.body && document.readyState === 'complete')`)) break;
        await delay(500);
      }
      if (await evaluate('location.origin') !== new URL(url).origin) throw new Error('Detector left its expected origin');
      result.environment = await evaluate(`({
        userAgent: navigator.userAgent, language: navigator.language, languages: navigator.languages,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        locale: Intl.DateTimeFormat().resolvedOptions().locale,
        timezoneOffsetMinutes: new Date().getTimezoneOffset(), platform: navigator.platform,
        webdriver: navigator.webdriver, hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemory: navigator.deviceMemory, doNotTrack: navigator.doNotTrack,
        screen: { width: screen.width, height: screen.height, devicePixelRatio },
      })`);
      if (mode === 'run' && name === 'fuck-claude') {
        const point = await evaluate(`(() => {
          const b = [...document.querySelectorAll('button')].find(b => /^(Start scan|开始检测|开始扫描)$/i.test(b.innerText.trim()));
          if (!b || b.disabled) return null;
          b.scrollIntoView({ behavior: 'instant', block: 'center' });
          const r = b.getBoundingClientRect();
          const point = { x: r.x + r.width / 2, y: r.y + r.height / 2 };
          if (!b.contains(document.elementFromPoint(point.x, point.y))) return null;
          return point;
        })()`);
        if (!point) throw new Error('Scan button unavailable');
        await call('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point });
        await call('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', buttons: 1, clickCount: 1 });
        await call('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', buttons: 0, clickCount: 1 });
        result.scanTriggered = false;
        for (let i = 0; i < 12; i++) {
          await delay(250);
          result.scanTriggered = await evaluate(`Boolean(document.getElementById('retest')?.disabled || !/^(Ready to scan|待检测|准备检测)$/.test(document.getElementById('risk-badge')?.innerText.trim() ?? 'Ready to scan'))`);
          if (result.scanTriggered) break;
        }
        if (!result.scanTriggered) throw new Error('Scan did not acknowledge the button click');
      }
      let previous = '', stable = 0;
      for (let i = 0; i < (mode === 'inspect' ? 3 : 16); i++) {
        await delay(4000);
        const state = await evaluate(`({
          body: document.body.innerText,
          byId: Object.fromEntries([...document.querySelectorAll('[id]')].map(e => [e.id, e.innerText ?? ''])),
          retestDisabled: document.getElementById('retest')?.disabled,
        })`);
        const current = state.body;
        result.detection = detectorResult(name, state, Boolean(result.scanTriggered));
        result.completed = mode === 'run' && result.detection.completed;
        stable = current === previous ? stable + 1 : 0;
        previous = current;
        if (mode === 'run' && i >= 2 && stable >= 1 && result.completed) break;
      }
      result.finalUrl = await evaluate('location.href');
      if (new URL(result.finalUrl).origin !== new URL(url).origin) throw new Error('Detector left its expected origin');
      result.title = await evaluate('document.title');
      result.buttons = await evaluate(`[...document.querySelectorAll('button')].map(b => ({text: b.innerText, disabled: b.disabled, id: b.id}))`);
      const structure = await evaluate(`[...document.querySelectorAll('[id]')].slice(0, 200).map(e => ({ id: e.id, text: e.innerText?.slice(0, 300) }))`);
      await writeFile(`${output}/${name}-structure.json`, JSON.stringify(structure, null, 2), { mode: 0o640 });
      await writeFile(`${output}/${name}.txt`, previous, { mode: 0o640 });
      const { data } = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
      await writeFile(`${output}/${name}.png`, Buffer.from(data, 'base64'), { mode: 0o640 });
      const { cssContentSize } = await call('Page.getLayoutMetrics');
      const full = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
        clip: { x: 0, y: 0, width: Math.min(cssContentSize.width, 2000), height: Math.min(cssContentSize.height, 16000), scale: 1 } });
      await writeFile(`${output}/${name}-full.png`, Buffer.from(full.data, 'base64'), { mode: 0o640 });
      result.snapshotSaved = true;
      if (mode === 'run' && !result.completed) result.error = 'Detector completion timeout';
    } catch (error) { result.error = safeError(error); }
    finally {
      result.finishedAt = new Date().toISOString();
      cdp.listeners.delete(onEvent);
      await cdp.call('Target.closeTarget', { targetId }).catch(() => {});
    }
    console.log(`${name}: HTTP=${result.httpStatus ?? 'unknown'} snapshot=${Boolean(result.snapshotSaved)} completed=${result.completed}`);
  }
} catch (error) { report.error = safeError(error); process.exitCode = 1; }
finally {
  cdp?.close();
  await writeFile(`${output}/report.json`, JSON.stringify(report, null, 2) + '\n', { mode: 0o640 });
  console.log(`REPORT=/srv/agentbox/site-check/output/${runId}/report.json`);
}
if (report.results.length !== targets.length || report.results.some(r => !r.snapshotSaved || (mode === 'run' && !r.completed))) process.exitCode = 1;
