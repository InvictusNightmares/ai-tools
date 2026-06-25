#!/usr/bin/env node

import crypto from "node:crypto";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const DEFAULT_ENDPOINT = "https://web.tabbit.ai/api/v1/chat/completion";
const DEFAULT_MODEL = "Claude-Opus-4.8";
const DEFAULT_REQ_CTX = "MS4xLjM5KDEwMTAxMDM5KQ==";
const DEFAULT_SESSION_ID = "58fb34e0-3151-4aa6-95cb-aeccbf0fb51f";
const DEFAULT_COOKIE_FILE = resolve(scriptDir, ".tabbit-cookie.local");
const DEFAULT_CHROME_DEVICE_ID = "227e8eef-0e37-412b-b068-3f08cf0cc3f7";
const DEFAULT_USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36";
const TABBIT_UUID_DEFAULT_BROWSER_MARKER = "1";
const TABBIT_UUID_MARKER_POS = 5;
const TABBIT_UUID_TIMESTAMP_POSITIONS = [2, 7, 11, 14, 18, 21, 25, 28];

function usage(exitCode = 0) {
  const out = exitCode === 0 ? console.log : console.error;
  out(`Usage:
  script/tabbit/chat-probe
  TABBIT_COOKIE='NEXT_LOCALE=...; token=...' script/tabbit/chat-probe --session <chat_session_id> --message "222"

Required:
  Cookie is read from TABBIT_COOKIE, TABBIT_COOKIE_FILE, or:
    ${DEFAULT_COOKIE_FILE}

Useful options:
  --session <id>                Chat session id. Default: ${DEFAULT_SESSION_ID}
  --message <text>              Message content. Default: 222
  --model <name>                Selected model. Default: ${DEFAULT_MODEL}
  --endpoint <url>              Endpoint. Default: ${DEFAULT_ENDPOINT}
  --timeout-ms <ms>             Request timeout. Default: 120000
  --dry-run                     Print a redacted request preview and do not send.

Optional replay headers:
  TABBIT_CHROME_ID_CONSISTENCY_REQUEST
  TABBIT_CHROME_CLIENT_ID
  TABBIT_CHROME_DEVICE_ID
  TABBIT_CHROME_SYNC_ACCOUNT_ID
  TABBIT_DISABLE_CHROME_ID=1
  TABBIT_X_NONCE
  TABBIT_X_TIMESTAMP
  TABBIT_X_SIGNATURE
  TABBIT_TRACE_ID
  TABBIT_UNIQUE_UUID
  TABBIT_IS_DEFAULT_BROWSER=1
  TABBIT_X_REQ_CTX

Optional body overrides:
  TABBIT_BODY_JSON              Full JSON request body override.
  TABBIT_REFERENCES_JSON        JSON array for references.
  TABBIT_INCLUDE_REFERENCE=1    Add a small current-webpage reference.
  TABBIT_COOKIE_FILE            Read Cookie value from a custom local file.
`);
  process.exit(exitCode);
}

function parseArgs(argv) {
  const args = {};
  const positional = [];

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "-h" || arg === "--help") {
      args.help = true;
      continue;
    }
    if (!arg.startsWith("--")) {
      positional.push(arg);
      continue;
    }

    const eq = arg.indexOf("=");
    const rawName = eq === -1 ? arg.slice(2) : arg.slice(2, eq);
    const name = rawName.replace(/-([a-z])/g, (_, char) => char.toUpperCase());
    if (eq !== -1) {
      args[name] = arg.slice(eq + 1);
      continue;
    }
    const next = argv[i + 1];
    if (next && !next.startsWith("--")) {
      args[name] = next;
      i += 1;
    } else {
      args[name] = true;
    }
  }

  if (positional.length > 0 && args.message === undefined) {
    args.message = positional.join(" ");
  }
  return args;
}

function parseJsonSetting(name, fallback) {
  const value = process.env[name];
  if (!value) return fallback;
  try {
    return JSON.parse(value);
  } catch (error) {
    console.error(`${name} is not valid JSON: ${error.message}`);
    process.exit(1);
  }
}

function parsePositiveInt(value, fallback, label) {
  if (value === undefined || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    console.error(`${label} must be a positive integer.`);
    process.exit(1);
  }
  return parsed;
}

function parseNullable(value) {
  if (value === undefined || value === "" || value === "null") return null;
  return value;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function stripHeaderPrefix(value, headerName) {
  const trimmed = value.trim();
  const prefix = `${headerName}:`;
  return trimmed.toLowerCase().startsWith(prefix.toLowerCase())
    ? trimmed.slice(prefix.length).trim()
    : trimmed;
}

function getCookieValue(cookie, name) {
  return cookie
    .split(/;\s*/)
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

function parseJwtPayload(token) {
  if (!token) return null;
  try {
    const [, payload] = token.split(".");
    if (!payload) return null;
    return JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
  } catch {
    return null;
  }
}

function randomHexChar(chars = "0123456789abcdef") {
  return chars[crypto.randomInt(0, chars.length)];
}

function buildTabbitUniqueUuid({ isDefaultBrowser = true } = {}) {
  const hexChars = "0123456789abcdef";
  const nonDefaultMarkerChars = hexChars.replace(TABBIT_UUID_DEFAULT_BROWSER_MARKER, "");
  const timestampHex = Math.floor(Date.now() / 1000)
    .toString(16)
    .padStart(TABBIT_UUID_TIMESTAMP_POSITIONS.length, "0")
    .slice(-TABBIT_UUID_TIMESTAMP_POSITIONS.length);
  const timestampByPosition = new Map(
    TABBIT_UUID_TIMESTAMP_POSITIONS.map((position, index) => [position, timestampHex[index]]),
  );

  let raw = "";
  for (let index = 0; index < 32; index += 1) {
    if (index === TABBIT_UUID_MARKER_POS) {
      raw += isDefaultBrowser ? TABBIT_UUID_DEFAULT_BROWSER_MARKER : randomHexChar(nonDefaultMarkerChars);
    } else if (timestampByPosition.has(index)) {
      raw += timestampByPosition.get(index);
    } else {
      raw += randomHexChar();
    }
  }

  return [raw.slice(0, 8), raw.slice(8, 12), raw.slice(12, 16), raw.slice(16, 20), raw.slice(20)].join("-");
}

async function readSetting(name, fileName, defaultFilePath = "") {
  if (process.env[name]) return process.env[name];
  const filePath = process.env[fileName] || defaultFilePath;
  if (!filePath) return "";
  try {
    return await readFile(filePath, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return "";
    throw error;
  }
}

function timeoutSignal(timeoutMs) {
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    return AbortSignal.timeout(timeoutMs);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  timer.unref?.();
  return controller.signal;
}

function buildReferences({ args, content, pageUrl }) {
  const references = parseJsonSetting("TABBIT_REFERENCES_JSON", null);
  if (references !== null) {
    if (!Array.isArray(references)) {
      console.error("TABBIT_REFERENCES_JSON must be a JSON array.");
      process.exit(1);
    }
    return references;
  }

  if (process.env.TABBIT_INCLUDE_REFERENCE !== "1") return [];

  return [
    {
      type: "current-webpage",
      title: args.referenceTitle ?? process.env.TABBIT_REFERENCE_TITLE ?? "current page",
      content: process.env.TABBIT_REFERENCE_CONTENT ?? content,
      metadata: {
        path: args.referenceUrl ?? process.env.TABBIT_REFERENCE_URL ?? pageUrl,
      },
    },
  ];
}

function buildBody({ args, sessionId, content, model, pageUrl }) {
  const override = parseJsonSetting("TABBIT_BODY_JSON", null);
  if (override !== null) return override;

  return {
    chat_session_id: sessionId,
    message_id: parseNullable(process.env.TABBIT_MESSAGE_ID),
    content,
    selected_model: model,
    parallel_group_id: parseNullable(process.env.TABBIT_PARALLEL_GROUP_ID),
    task_name: process.env.TABBIT_TASK_NAME ?? "chat",
    agent_mode: process.env.TABBIT_AGENT_MODE === "1",
    metadatas: {
      html_content: process.env.TABBIT_HTML_CONTENT ?? `<p>${escapeHtml(content)}</p>`,
    },
    references: buildReferences({ args, content, pageUrl }),
    entity: {
      key: process.env.TABBIT_ENTITY_KEY ?? crypto.randomBytes(16).toString("hex"),
      extras: {
        type: process.env.TABBIT_ENTITY_TYPE ?? "tab",
        url: pageUrl,
      },
    },
  };
}

function buildChromeIdConsistencyHeader(cookie) {
  if (process.env.TABBIT_DISABLE_CHROME_ID === "1") return "";
  if (process.env.TABBIT_CHROME_ID_CONSISTENCY_REQUEST) {
    return stripHeaderPrefix(process.env.TABBIT_CHROME_ID_CONSISTENCY_REQUEST, "X-Chrome-ID-Consistency-Request");
  }

  const tokenPayload = parseJwtPayload(getCookieValue(cookie, "token"));
  const clientId = process.env.TABBIT_CHROME_CLIENT_ID ?? tokenPayload?.azp;
  const syncAccountId =
    process.env.TABBIT_CHROME_SYNC_ACCOUNT_ID ?? tokenPayload?.sub ?? tokenPayload?.id ?? getCookieValue(cookie, "user_id");
  const deviceId = process.env.TABBIT_CHROME_DEVICE_ID ?? DEFAULT_CHROME_DEVICE_ID;
  if (!clientId || !syncAccountId || !deviceId) return "";

  return [
    "version=1",
    `client_id=${clientId}`,
    `device_id=${deviceId}`,
    `sync_account_id=${syncAccountId}`,
    `signin_mode=${process.env.TABBIT_CHROME_SIGNIN_MODE ?? "all_accounts"}`,
    `signout_mode=${process.env.TABBIT_CHROME_SIGNOUT_MODE ?? "show_confirmation"}`,
  ].join(",");
}

function buildHeaders({ cookie, refererSessionId }) {
  const isDefaultBrowser = process.env.TABBIT_IS_DEFAULT_BROWSER !== "0";
  const headers = {
    "cache-control": "no-cache",
    "sec-ch-ua-platform": '"macOS"',
    "sec-ch-ua": '"Chromium";v="148", "Tabbit";v="148", "Not/A)Brand";v="99"',
    "x-nonce": process.env.TABBIT_X_NONCE ?? crypto.randomBytes(32).toString("hex"),
    "trace-id": process.env.TABBIT_TRACE_ID ?? crypto.randomUUID(),
    "x-timestamp": process.env.TABBIT_X_TIMESTAMP ?? String(Date.now()),
    "unique-uuid": process.env.TABBIT_UNIQUE_UUID ?? buildTabbitUniqueUuid({ isDefaultBrowser }),
    "x-req-ctx": process.env.TABBIT_X_REQ_CTX ?? DEFAULT_REQ_CTX,
    "sec-ch-ua-mobile": "?0",
    "x-signature": process.env.TABBIT_X_SIGNATURE ?? crypto.randomUUID(),
    "user-agent": process.env.TABBIT_USER_AGENT ?? DEFAULT_USER_AGENT,
    accept: "text/event-stream",
    "content-type": "application/json",
    origin: "https://web.tabbit.ai",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    referer: process.env.TABBIT_REFERER ?? `https://web.tabbit.ai/panel/${refererSessionId}`,
    "accept-language": process.env.TABBIT_ACCEPT_LANGUAGE ?? "zh-CN,zh;q=0.9",
    cookie,
    "x-glic": process.env.TABBIT_X_GLIC ?? "1",
    "x-glic-chrome-version": process.env.TABBIT_GLIC_CHROME_VERSION ?? "148.0.7778.168",
    "x-glic-chrome-channel": process.env.TABBIT_GLIC_CHROME_CHANNEL ?? "unknown",
  };

  const chromeIdConsistency = buildChromeIdConsistencyHeader(cookie);
  if (chromeIdConsistency) headers["X-Chrome-ID-Consistency-Request"] = chromeIdConsistency;
  if (process.env.TABBIT_BAGGAGE) headers.baggage = process.env.TABBIT_BAGGAGE;
  if (process.env.TABBIT_SENTRY_TRACE) headers["sentry-trace"] = process.env.TABBIT_SENTRY_TRACE;

  return headers;
}

async function printResponse(response) {
  console.log(`HTTP ${response.status} ${response.statusText}`);
  console.log(`content-type: ${response.headers.get("content-type") ?? "(none)"}`);
  console.log("");

  if (!response.body) {
    const text = await response.text();
    process.stdout.write(text);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    process.stdout.write(decoder.decode(value, { stream: true }));
  }
  process.stdout.write(decoder.decode());
}

const args = parseArgs(process.argv.slice(2));
if (args.help) usage(0);

const cookie = stripHeaderPrefix(
  await readSetting("TABBIT_COOKIE", "TABBIT_COOKIE_FILE", DEFAULT_COOKIE_FILE),
  "Cookie",
);
const sessionId = args.session ?? process.env.TABBIT_SESSION_ID ?? DEFAULT_SESSION_ID;
if (!cookie || !sessionId) {
  console.error("Missing TABBIT_COOKIE or --session/TABBIT_SESSION_ID.\n");
  usage(1);
}

const endpoint = args.endpoint ?? process.env.TABBIT_ENDPOINT ?? DEFAULT_ENDPOINT;
const content = String(args.message ?? process.env.TABBIT_MESSAGE ?? "222");
const model = args.model ?? process.env.TABBIT_MODEL ?? DEFAULT_MODEL;
const timeoutMs = parsePositiveInt(args.timeoutMs ?? process.env.TABBIT_TIMEOUT_MS, 120000, "timeout-ms");
const refererSessionId = process.env.TABBIT_REFERER_SESSION_ID ?? sessionId;
const pageUrl = args.pageUrl ?? process.env.TABBIT_PAGE_URL ?? `https://web.tabbit.ai/panel/${sessionId}`;
const body = buildBody({ args, sessionId, content, model, pageUrl });
const headers = buildHeaders({ cookie, refererSessionId });

if (args.dryRun || process.env.TABBIT_DRY_RUN === "1") {
  console.log(
    JSON.stringify(
      {
        method: "POST",
        endpoint,
        headers: { ...headers, cookie: "<redacted>" },
        body,
      },
      null,
      2,
    ),
  );
  process.exit(0);
}

console.error(`POST ${endpoint}`);
console.error(`session: ${sessionId}`);
console.error(`model: ${model}`);
console.error(`message chars: ${content.length}`);
console.error("");

try {
  const response = await fetch(endpoint, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: timeoutSignal(timeoutMs),
  });
  await printResponse(response);
  if (!response.ok) process.exitCode = 1;
} catch (error) {
  console.error(`Request failed: ${error.name === "TimeoutError" ? "timeout" : error.message}`);
  process.exit(1);
}
