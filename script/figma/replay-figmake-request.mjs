#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const FIGMAKE_URL = "https://www.figma.com/api/cortex/shared/figmake";
const DEFAULT_CURL_FILE = fileURLToPath(
  new URL("./local/figmake-request.curl", import.meta.url),
);
const DEFAULT_COOKIE_FILE = fileURLToPath(
  new URL("./.figma-cookie.local", import.meta.url),
);
const MINIMAL_HEADER_NAMES = new Set([
  "content-type",
  "user-agent",
  "x-figma-file-key",
  "x-figma-user-id",
]);
const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-length",
  "host",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function printUsage() {
  console.log(`Usage:
  # Replay the locally captured request directly
  node script/figma/replay-figmake-request.mjs [options]

Options:
  --curl-file <path>  Override local/figmake-request.curl
  --cookie-file <path> Override .figma-cookie.local
  --prompt <text>     Replace the captured user prompt before sending
  --model <id>        Override the captured model
  --minimal           Send only the proven minimum headers and body fields
  --dry-run           Parse and summarize the request without sending it
  --help              Show this help

The local capture and cookie files are git-ignored and are never printed.`);
}

function parseArgs(argv) {
  const options = {
    curlFile: null,
    cookieFile: DEFAULT_COOKIE_FILE,
    prompt: null,
    model: null,
    minimal: false,
    dryRun: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];

    if (argument === "--help" || argument === "-h") {
      printUsage();
      process.exit(0);
    }

    if (argument === "--dry-run") {
      options.dryRun = true;
      continue;
    }

    if (argument === "--minimal") {
      options.minimal = true;
      continue;
    }

    if (argument === "--curl-file") {
      options.curlFile = argv[++index];
      if (!options.curlFile) {
        throw new Error("--curl-file requires a path");
      }
      continue;
    }

    if (argument === "--cookie-file") {
      options.cookieFile = argv[++index];
      if (!options.cookieFile) {
        throw new Error("--cookie-file requires a path");
      }
      continue;
    }

    if (argument === "--prompt") {
      options.prompt = argv[++index];
      if (options.prompt === undefined) {
        throw new Error("--prompt requires text");
      }
      continue;
    }

    if (argument === "--model") {
      options.model = argv[++index];
      if (!options.model) {
        throw new Error("--model requires an ID");
      }
      continue;
    }

    throw new Error(`Unknown option: ${argument}`);
  }

  return options;
}

function readCurlCommand(curlFile) {
  if (curlFile === "-") {
    return readFileSync(0, "utf8");
  }

  if (curlFile) {
    return readFileSync(curlFile, "utf8");
  }

  if (existsSync(DEFAULT_CURL_FILE)) {
    return readFileSync(DEFAULT_CURL_FILE, "utf8");
  }

  if (process.platform !== "darwin") {
    throw new Error("Clipboard input is only supported on macOS; use --curl-file");
  }

  try {
    return execFileSync("/usr/bin/pbpaste", [], {
      encoding: "utf8",
      maxBuffer: 20 * 1024 * 1024,
    });
  } catch {
    throw new Error(
      "Could not read the clipboard. Copy the request as cURL in Proxyman, then retry.",
    );
  }
}

function readCookie(cookieFile) {
  if (!existsSync(cookieFile)) {
    throw new Error(`Cookie file not found: ${cookieFile}`);
  }

  const cookie = readFileSync(cookieFile, "utf8")
    .trim()
    .replace(/^Cookie:\s*/i, "");

  if (!cookie) {
    throw new Error(`Cookie file is empty: ${cookieFile}`);
  }

  return cookie;
}

function tokenizeShell(command) {
  const tokens = [];
  let token = "";
  let quote = null;
  let tokenStarted = false;

  for (let index = 0; index < command.length; index += 1) {
    const character = command[index];

    if (quote === "'") {
      if (character === "'") {
        quote = null;
      } else {
        token += character;
      }
      tokenStarted = true;
      continue;
    }

    if (quote === '"') {
      if (character === '"') {
        quote = null;
      } else if (character === "\\") {
        const next = command[index + 1];
        if (next === "\n") {
          index += 1;
        } else if (next === "\r" && command[index + 2] === "\n") {
          index += 2;
        } else if (next !== undefined) {
          token += next;
          index += 1;
        }
      } else {
        token += character;
      }
      tokenStarted = true;
      continue;
    }

    if (character === "'" || character === '"') {
      quote = character;
      tokenStarted = true;
      continue;
    }

    if (character === "\\") {
      const next = command[index + 1];
      if (next === "\n") {
        index += 1;
      } else if (next === "\r" && command[index + 2] === "\n") {
        index += 2;
      } else if (next !== undefined) {
        token += next;
        index += 1;
        tokenStarted = true;
      }
      continue;
    }

    if (/\s/.test(character)) {
      if (tokenStarted) {
        tokens.push(token);
        token = "";
        tokenStarted = false;
      }
      continue;
    }

    token += character;
    tokenStarted = true;
  }

  if (quote) {
    throw new Error("The copied cURL contains an unterminated quote");
  }

  if (tokenStarted) {
    tokens.push(token);
  }

  return tokens;
}

function parseCurl(command) {
  const tokens = tokenizeShell(command.trim());
  if (!tokens[0] || !/(^|\/)curl$/.test(tokens[0])) {
    throw new Error(
      "Input is not a cURL command. Copy cURL in Proxyman after preparing the Terminal command; copying the Terminal command again overwrites the cURL.",
    );
  }

  let url = null;
  let method = null;
  let body = null;
  const headers = [];

  for (let index = 1; index < tokens.length; index += 1) {
    const token = tokens[index];

    if (token === "-X" || token === "--request") {
      method = tokens[++index];
      continue;
    }

    if (token === "-H" || token === "--header") {
      const header = tokens[++index];
      const separator = header?.indexOf(":") ?? -1;
      if (separator <= 0) {
        throw new Error(`Invalid cURL header: ${header}`);
      }
      headers.push([
        header.slice(0, separator).trim(),
        header.slice(separator + 1).trim(),
      ]);
      continue;
    }

    if (
      token === "--data" ||
      token === "--data-raw" ||
      token === "--data-binary" ||
      token === "-d"
    ) {
      body = tokens[++index];
      continue;
    }

    if (token === "--url") {
      url = tokens[++index];
      continue;
    }

    if (!token.startsWith("-") && !url) {
      url = token;
    }
  }

  if (!url) {
    throw new Error("No URL found in the copied cURL");
  }

  return {
    url,
    method: method ?? (body === null ? "GET" : "POST"),
    headers,
    body,
  };
}

function replacePrompt(body, prompt) {
  const payload = JSON.parse(body);
  const userMessage = [...(payload.aiChatMessages ?? [])]
    .reverse()
    .find((message) => message.role === "user");
  const textPart = userMessage?.content?.find((part) => part.type === "text");

  if (!userMessage || !textPart) {
    throw new Error("Could not locate the user message in the captured body");
  }

  textPart.text = prompt;
  userMessage.createdAtMs = Date.now();
  userMessage.scenegraphSentAt = String(Date.now());

  if (payload.rawUserChatDetails) {
    payload.rawUserChatDetails.rawUserMessage = prompt;
  }

  if (payload.userMessageContent) {
    payload.userMessageContent.plainText = prompt;
  }

  return JSON.stringify(payload);
}

function buildBody(body, options) {
  let payload = JSON.parse(body);

  if (options.prompt !== null) {
    payload = JSON.parse(replacePrompt(JSON.stringify(payload), options.prompt));
  }
  if (options.model !== null) {
    payload.model = options.model;
  }

  if (!options.minimal) {
    return options.prompt === null && options.model === null
      ? body
      : JSON.stringify(payload);
  }

  const userMessage = [...(payload.aiChatMessages ?? [])]
    .reverse()
    .find((message) => message.role === "user");
  if (!userMessage) {
    throw new Error("Could not locate the user message in the captured body");
  }

  return JSON.stringify({
    model: payload.model,
    aiChatMessages: [userMessage],
    files: {},
    chats: [],
  });
}

function buildHeaders(capturedHeaders, cookie, minimal) {
  const headers = new Headers();

  for (const [name, value] of capturedHeaders) {
    const normalizedName = name.toLowerCase();
    if (
      !HOP_BY_HOP_HEADERS.has(normalizedName) &&
      (!minimal || MINIMAL_HEADER_NAMES.has(normalizedName))
    ) {
      headers.append(name, value);
    }
  }

  headers.set("Cookie", cookie);
  return headers;
}

function summarize(request, body, minimal) {
  let parsedBody = null;
  try {
    parsedBody = body ? JSON.parse(body) : null;
  } catch {
    // The request can still be replayed even if the body is not JSON.
  }

  const headerNames = [
    ...new Set(
      request.headers
        .map(([name]) => name.toLowerCase())
        .filter(
          (name) =>
            !HOP_BY_HOP_HEADERS.has(name) &&
            (!minimal || MINIMAL_HEADER_NAMES.has(name)),
        )
        .concat("cookie"),
    ),
  ].sort();

  console.error(`Target: ${request.method} ${request.url}`);
  console.error(`Headers: ${headerNames.join(", ")}`);
  console.error(`Body bytes: ${Buffer.byteLength(body ?? "")}`);

  if (parsedBody) {
    const userMessage = [...(parsedBody.aiChatMessages ?? [])]
      .reverse()
      .find((message) => message.role === "user");
    const prompt =
      parsedBody.userMessageContent?.plainText ??
      userMessage?.content?.find((part) => part.type === "text")?.text ??
      null;

    console.error(`Body fields: ${Object.keys(parsedBody).join(", ")}`);
    console.error(`Captured prompt: ${JSON.stringify(prompt)}`);
  }
}

async function replay(request, body, cookie, minimal) {
  const response = await fetch(request.url, {
    method: request.method,
    headers: buildHeaders(request.headers, cookie, minimal),
    body: ["GET", "HEAD"].includes(request.method.toUpperCase())
      ? undefined
      : body,
    redirect: "manual",
  });

  console.error(
    `Response: ${response.status} ${response.statusText} (${response.headers.get("content-type") ?? "unknown content type"})`,
  );

  if (!response.body) {
    return;
  }

  for await (const chunk of response.body) {
    process.stdout.write(Buffer.from(chunk));
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const captured = parseCurl(readCurlCommand(options.curlFile));
  const cookie = readCookie(options.cookieFile);
  const target = new URL(captured.url);

  if (
    target.origin + target.pathname !== FIGMAKE_URL ||
    captured.method.toUpperCase() !== "POST"
  ) {
    throw new Error(
      `Refusing to replay an unexpected request: ${captured.method} ${captured.url}`,
    );
  }

  const body = buildBody(captured.body, options);

  summarize(captured, body, options.minimal);

  if (!options.dryRun) {
    await replay(captured, body, cookie, options.minimal);
  }
}

main().catch((error) => {
  console.error(`Error: ${error.message}`);
  process.exitCode = 1;
});
