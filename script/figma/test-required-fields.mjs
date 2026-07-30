#!/usr/bin/env node

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const ENDPOINT = "https://www.figma.com/api/cortex/shared/figmake";
const CURL_FILE = fileURLToPath(
  new URL("./local/figmake-request.curl", import.meta.url),
);
const COOKIE_FILE = fileURLToPath(
  new URL("./.figma-cookie.local", import.meta.url),
);
const PROMPT = "只回复 OK，不修改文件。";
const CASE_NAME = process.argv[2];
const ALLOWED_CASES = new Set([
  "model-prompt",
  "model-user-content",
  "model-ai-message",
  "message-core",
  "runtime-core",
  "runtime-plus-chat",
  "runtime-plus-conversation",
  "runtime-plus-thread",
  "runtime-plus-chats",
  "runtime-plus-thread-id",
  "runtime-plus-message-count",
  "runtime-plus-chats-thread-id",
  "runtime-plus-chats-count",
  "runtime-plus-thread-id-count",
  "runtime-minimal",
  "runtime-no-file-context",
  "runtime-no-routing",
  "runtime-ai-message-only",
  "runtime-compact",
  "compact-no-files",
  "compact-no-snapshot-options",
  "compact-no-sbox",
  "compact-minimal",
  "compact-without-files-field",
  "compact-without-file-metadata",
  "minimal-six",
  "minimal-no-model",
  "minimal-no-agent",
  "minimal-no-ai-messages",
  "minimal-no-chats",
  "minimal-no-thread-id",
  "minimal-three",
  "minimal-three-minimal-headers",
  "minimal-three-browser-headers",
  "minimal-three-figma-headers",
  "minimal-three-essential-headers",
  "minimal-three-essential-file-headers",
  "minimal-three-browser-user-headers",
  "minimal-message-shape",
  "runtime-plus-chat-sdk",
  "runtime-plus-integrations",
  "runtime-plus-platform",
  "runtime-no-fs-options",
  "runtime-no-sbox",
  "runtime-no-scope",
  "full-no-files",
  "full",
]);

if (!ALLOWED_CASES.has(CASE_NAME)) {
  console.error(
    `Usage: node script/figma/test-required-fields.mjs <${[...ALLOWED_CASES].join("|")}>`,
  );
  process.exit(1);
}

function parseCapture() {
  const curl = readFileSync(CURL_FILE, "utf8");
  const marker = "--data-raw '";
  const start = curl.indexOf(marker);
  if (start < 0) {
    throw new Error("Captured cURL has no --data-raw body");
  }

  const body = curl.slice(start + marker.length, curl.lastIndexOf("'"));
  const payload = JSON.parse(body.replace(/'\\''/g, "'"));
  const headers = new Headers();

  for (const match of curl.matchAll(/-H '([^:']+):\s*([^']*)'/g)) {
    const name = match[1];
    if (
      !["host", "connection", "content-length", "accept-encoding"].includes(
        name.toLowerCase(),
      )
    ) {
      headers.set(name, match[2]);
    }
  }

  const cookie = readFileSync(COOKIE_FILE, "utf8")
    .trim()
    .replace(/^Cookie:\s*/i, "");
  if (!cookie) {
    throw new Error("Cookie file is empty");
  }
  headers.set("Cookie", cookie);

  return { payload, headers };
}

function prepareMessage(source) {
  const message = structuredClone(
    [...source.aiChatMessages]
      .reverse()
      .find((candidate) => candidate.role === "user"),
  );
  const text = message.content.find((part) => part.type === "text");
  text.text = PROMPT;
  message.createdAtMs = Date.now();
  message.scenegraphSentAt = String(Date.now());
  return message;
}

function buildPayload(source) {
  const userMessageContent = {
    ...source.userMessageContent,
    plainText: PROMPT,
  };
  const rawUserChatDetails = {
    ...source.rawUserChatDetails,
    rawUserMessage: PROMPT,
  };
  const aiChatMessages = [prepareMessage(source)];

  switch (CASE_NAME) {
    case "model-prompt":
      return {
        model: source.model,
        prompt: PROMPT,
      };
    case "model-user-content":
      return {
        model: source.model,
        userMessageContent,
      };
    case "model-ai-message":
      return {
        model: source.model,
        aiChatMessages,
      };
    case "message-core":
      return {
        model: source.model,
        agentId: source.agentId,
        aiChatMessages,
        rawUserChatDetails,
        userMessageContent,
      };
    case "minimal-message-shape":
      return {
        aiChatMessages: [
          {
            role: "user",
            content: [{ type: "text", text: PROMPT }],
          },
        ],
        files: {},
        chats: [],
      };
    case "runtime-core":
    case "runtime-plus-chat":
    case "runtime-plus-conversation":
    case "runtime-plus-thread":
    case "runtime-plus-chats":
    case "runtime-plus-thread-id":
    case "runtime-plus-message-count":
    case "runtime-plus-chats-thread-id":
    case "runtime-plus-chats-count":
    case "runtime-plus-thread-id-count":
    case "runtime-minimal":
    case "runtime-no-file-context":
    case "runtime-no-routing":
    case "runtime-ai-message-only":
    case "runtime-compact":
    case "compact-no-files":
    case "compact-no-snapshot-options":
    case "compact-no-sbox":
    case "compact-minimal":
    case "compact-without-files-field":
    case "compact-without-file-metadata":
    case "minimal-six":
    case "minimal-no-model":
    case "minimal-no-agent":
    case "minimal-no-ai-messages":
    case "minimal-no-chats":
    case "minimal-no-thread-id":
    case "minimal-three":
    case "minimal-three-minimal-headers":
    case "minimal-three-browser-headers":
    case "minimal-three-figma-headers":
    case "minimal-three-essential-headers":
    case "minimal-three-essential-file-headers":
    case "minimal-three-browser-user-headers":
    case "runtime-plus-chat-sdk":
    case "runtime-plus-integrations":
    case "runtime-plus-platform":
    case "runtime-no-fs-options":
    case "runtime-no-sbox":
    case "runtime-no-scope": {
      const payload = {
        model: source.model,
        agentId: source.agentId,
        aiChatMessages,
        rawUserChatDetails,
        userMessageContent,
        files: {},
        fileMetadata: [],
        productType: source.productType,
        featureType: source.featureType,
        codeLibraryFormat: source.codeLibraryFormat,
        sboxdUrl: source.sboxdUrl,
        scopeType: source.scopeType,
        scopeKey: source.scopeKey,
        startFileSeqNum: source.startFileSeqNum,
        fsSnapshotOptions: source.fsSnapshotOptions,
      };

      if (CASE_NAME === "runtime-plus-chat") {
        Object.assign(payload, {
          chats: source.chats,
          aiChatThreadId: source.aiChatThreadId,
          numNewAiChatMessages: source.numNewAiChatMessages,
          chatSdkEnabled: source.chatSdkEnabled,
          chatCompression: source.chatCompression,
          supabase: source.supabase,
          supabaseEnabled: source.supabaseEnabled,
          todoAutoAccept: source.todoAutoAccept,
          codeLibraryComponents: source.codeLibraryComponents,
        });
      }
      if (CASE_NAME === "runtime-plus-conversation") {
        Object.assign(payload, {
          chats: source.chats,
          aiChatThreadId: source.aiChatThreadId,
          numNewAiChatMessages: source.numNewAiChatMessages,
          chatSdkEnabled: source.chatSdkEnabled,
          chatCompression: source.chatCompression,
        });
      }
      if (CASE_NAME === "runtime-plus-thread") {
        Object.assign(payload, {
          chats: source.chats,
          aiChatThreadId: source.aiChatThreadId,
          numNewAiChatMessages: source.numNewAiChatMessages,
        });
      }
      if (CASE_NAME === "runtime-plus-chats") {
        payload.chats = source.chats;
      }
      if (CASE_NAME === "runtime-plus-thread-id") {
        payload.aiChatThreadId = source.aiChatThreadId;
      }
      if (CASE_NAME === "runtime-plus-message-count") {
        payload.numNewAiChatMessages = source.numNewAiChatMessages;
      }
      if (CASE_NAME === "runtime-plus-chats-thread-id") {
        payload.chats = source.chats;
        payload.aiChatThreadId = source.aiChatThreadId;
      }
      if (CASE_NAME === "runtime-plus-chats-count") {
        payload.chats = source.chats;
        payload.numNewAiChatMessages = source.numNewAiChatMessages;
      }
      if (CASE_NAME === "runtime-plus-thread-id-count") {
        payload.aiChatThreadId = source.aiChatThreadId;
        payload.numNewAiChatMessages = source.numNewAiChatMessages;
      }
      if (
        [
          "runtime-minimal",
          "runtime-no-file-context",
          "runtime-no-routing",
          "runtime-ai-message-only",
          "runtime-compact",
          "compact-no-files",
          "compact-no-snapshot-options",
          "compact-no-sbox",
          "compact-minimal",
          "compact-without-files-field",
          "compact-without-file-metadata",
          "minimal-six",
          "minimal-no-model",
          "minimal-no-agent",
          "minimal-no-ai-messages",
          "minimal-no-chats",
          "minimal-no-thread-id",
          "minimal-three",
          "minimal-three-minimal-headers",
        ].includes(CASE_NAME) || CASE_NAME.startsWith("minimal-three")
      ) {
        payload.chats = source.chats;
        payload.aiChatThreadId = source.aiChatThreadId;
      }
      if (CASE_NAME === "runtime-no-file-context") {
        delete payload.files;
        delete payload.fileMetadata;
        delete payload.startFileSeqNum;
        delete payload.fsSnapshotOptions;
      }
      if (CASE_NAME === "runtime-no-routing") {
        delete payload.productType;
        delete payload.featureType;
        delete payload.codeLibraryFormat;
        delete payload.scopeType;
        delete payload.scopeKey;
      }
      if (CASE_NAME === "runtime-ai-message-only") {
        delete payload.rawUserChatDetails;
        delete payload.userMessageContent;
      }
      if (CASE_NAME === "runtime-compact") {
        delete payload.rawUserChatDetails;
        delete payload.userMessageContent;
        delete payload.productType;
        delete payload.featureType;
        delete payload.codeLibraryFormat;
        delete payload.scopeType;
        delete payload.scopeKey;
      }
      if (
        [
          "compact-no-files",
          "compact-no-snapshot-options",
          "compact-no-sbox",
          "compact-minimal",
          "compact-without-files-field",
          "compact-without-file-metadata",
          "minimal-six",
          "minimal-no-model",
          "minimal-no-agent",
          "minimal-no-ai-messages",
          "minimal-no-chats",
          "minimal-no-thread-id",
          "minimal-three",
          "minimal-three-minimal-headers",
        ].includes(CASE_NAME) || CASE_NAME.startsWith("minimal-three")
      ) {
        delete payload.rawUserChatDetails;
        delete payload.userMessageContent;
        delete payload.productType;
        delete payload.featureType;
        delete payload.codeLibraryFormat;
        delete payload.scopeType;
        delete payload.scopeKey;
      }
      if (CASE_NAME === "compact-no-files") {
        delete payload.files;
        delete payload.fileMetadata;
      }
      if (CASE_NAME === "compact-no-snapshot-options") {
        delete payload.startFileSeqNum;
        delete payload.fsSnapshotOptions;
      }
      if (CASE_NAME === "compact-no-sbox") {
        delete payload.sboxdUrl;
      }
      if (
        [
          "compact-minimal",
          "compact-without-files-field",
          "compact-without-file-metadata",
        ].includes(CASE_NAME) || CASE_NAME.startsWith("minimal-three")
      ) {
        delete payload.sboxdUrl;
        delete payload.startFileSeqNum;
        delete payload.fsSnapshotOptions;
      }
      if (CASE_NAME === "compact-without-files-field") {
        delete payload.files;
      }
      if (CASE_NAME === "compact-without-file-metadata") {
        delete payload.fileMetadata;
      }
      if (
        [
          "minimal-six",
          "minimal-no-model",
          "minimal-no-agent",
          "minimal-no-ai-messages",
          "minimal-no-chats",
          "minimal-no-thread-id",
          "minimal-three",
          "minimal-three-minimal-headers",
        ].includes(CASE_NAME) || CASE_NAME.startsWith("minimal-three")
      ) {
        delete payload.sboxdUrl;
        delete payload.startFileSeqNum;
        delete payload.fsSnapshotOptions;
        delete payload.fileMetadata;
      }
      if (CASE_NAME === "minimal-no-model") {
        delete payload.model;
      }
      if (CASE_NAME === "minimal-no-agent") {
        delete payload.agentId;
      }
      if (CASE_NAME === "minimal-no-ai-messages") {
        delete payload.aiChatMessages;
      }
      if (CASE_NAME === "minimal-no-chats") {
        delete payload.chats;
      }
      if (CASE_NAME === "minimal-no-thread-id") {
        delete payload.aiChatThreadId;
      }
      if (CASE_NAME.startsWith("minimal-three")) {
        delete payload.model;
        delete payload.agentId;
        delete payload.aiChatThreadId;
      }
      if (CASE_NAME === "runtime-plus-chat-sdk") {
        Object.assign(payload, {
          chatSdkEnabled: source.chatSdkEnabled,
          chatCompression: source.chatCompression,
        });
      }
      if (CASE_NAME === "runtime-plus-integrations") {
        Object.assign(payload, {
          supabase: source.supabase,
          supabaseEnabled: source.supabaseEnabled,
          todoAutoAccept: source.todoAutoAccept,
          codeLibraryComponents: source.codeLibraryComponents,
        });
      }
      if (CASE_NAME === "runtime-plus-platform") {
        Object.assign(payload, {
          designSystemPackageScopes: source.designSystemPackageScopes,
          isKit: source.isKit,
          requestInitiator: source.requestInitiator,
          mcpPreferences: source.mcpPreferences,
          resumableMakeEnabled: source.resumableMakeEnabled,
          isMobileClient: source.isMobileClient,
          makeStartedOnPlatform: source.makeStartedOnPlatform,
          disableWebSearch: source.disableWebSearch,
          serverSideCommitEnabled: false,
          workloadConfig: source.workloadConfig,
        });
      }

      if (CASE_NAME === "runtime-no-fs-options") {
        delete payload.startFileSeqNum;
        delete payload.fsSnapshotOptions;
      }
      if (CASE_NAME === "runtime-no-sbox") {
        delete payload.sboxdUrl;
      }
      if (CASE_NAME === "runtime-no-scope") {
        delete payload.scopeType;
        delete payload.scopeKey;
      }
      return payload;
    }
    case "full-no-files": {
      const payload = structuredClone(source);
      payload.aiChatMessages = aiChatMessages;
      payload.rawUserChatDetails = rawUserChatDetails;
      payload.userMessageContent = userMessageContent;
      payload.files = {};
      payload.fileMetadata = [];
      payload.serverSideCommitEnabled = false;
      return payload;
    }
    case "full": {
      const payload = structuredClone(source);
      payload.aiChatMessages = aiChatMessages;
      payload.rawUserChatDetails = rawUserChatDetails;
      payload.userMessageContent = userMessageContent;
      payload.serverSideCommitEnabled = false;
      return payload;
    }
  }
}

const { payload: source, headers } = parseCapture();
const payload = buildPayload(source);

function pickHeaders(names) {
  const picked = new Headers();
  for (const name of names) {
    const value = headers.get(name);
    if (value !== null) {
      picked.set(name, value);
    }
  }
  return picked;
}

let requestHeaders = headers;
if (CASE_NAME === "minimal-three-minimal-headers") {
  requestHeaders = pickHeaders(["Content-Type", "Cookie"]);
}
if (CASE_NAME === "minimal-three-browser-headers") {
  requestHeaders = pickHeaders([
    "Content-Type",
    "Cookie",
    "Accept",
    "Accept-Language",
    "Origin",
    "Referer",
    "User-Agent",
    "sec-ch-ua",
    "sec-ch-ua-mobile",
    "sec-ch-ua-platform",
    "Sec-Fetch-Dest",
    "Sec-Fetch-Mode",
    "Sec-Fetch-Site",
  ]);
}
if (CASE_NAME === "minimal-three-figma-headers") {
  requestHeaders = new Headers({
    "Content-Type": headers.get("Content-Type"),
    Cookie: headers.get("Cookie"),
  });
  for (const [name, value] of headers) {
    if (
      name.startsWith("x-figma-") ||
      name.startsWith("x-referer-") ||
      name === "tsid"
    ) {
      requestHeaders.set(name, value);
    }
  }
}
if (CASE_NAME === "minimal-three-essential-headers") {
  requestHeaders = pickHeaders([
    "Content-Type",
    "Cookie",
    "User-Agent",
    "X-Figma-User-ID",
  ]);
}
if (CASE_NAME === "minimal-three-essential-file-headers") {
  requestHeaders = pickHeaders([
    "Content-Type",
    "Cookie",
    "User-Agent",
    "X-Figma-User-ID",
    "X-Figma-File-Key",
  ]);
}
if (CASE_NAME === "minimal-message-shape") {
  requestHeaders = pickHeaders([
    "Content-Type",
    "Cookie",
    "User-Agent",
    "X-Figma-User-ID",
    "X-Figma-File-Key",
  ]);
}
if (CASE_NAME === "minimal-three-browser-user-headers") {
  requestHeaders = pickHeaders([
    "Content-Type",
    "Cookie",
    "Accept",
    "Accept-Language",
    "Origin",
    "Referer",
    "User-Agent",
    "sec-ch-ua",
    "sec-ch-ua-mobile",
    "sec-ch-ua-platform",
    "Sec-Fetch-Dest",
    "Sec-Fetch-Mode",
    "Sec-Fetch-Site",
    "X-Figma-User-ID",
  ]);
}

if (process.argv.includes("--dry-run")) {
  console.log(
    JSON.stringify(
      {
        case: CASE_NAME,
        requestFields: Object.keys(payload),
        requestBytes: Buffer.byteLength(JSON.stringify(payload)),
      },
      null,
      2,
    ),
  );
  process.exit(0);
}

const response = await fetch(ENDPOINT, {
  method: "POST",
  headers: requestHeaders,
  body: JSON.stringify(payload),
});
const reader = response.body?.getReader();
const decoder = new TextDecoder();
let responseBytes = 0;
let responsePreview = "";
let applicationFinished = false;
let carry = "";

while (reader) {
  const { value, done } = await reader.read();
  if (done) {
    break;
  }

  responseBytes += value.byteLength;
  const text = decoder.decode(value, { stream: true });
  if (responsePreview.length < 2_000) {
    responsePreview += text.slice(0, 2_000 - responsePreview.length);
  }

  carry = (carry + text).slice(-4_000);
  if (carry.includes('"type":"finish"')) {
    applicationFinished = true;
    await reader.cancel();
    break;
  }
}

console.log(
  JSON.stringify(
    {
      case: CASE_NAME,
      requestFields: Object.keys(payload),
      requestBytes: Buffer.byteLength(JSON.stringify(payload)),
      status: response.status,
      contentType: response.headers.get("content-type"),
      responseBytes,
      applicationFinished,
      responsePreview,
    },
    null,
    2,
  ),
);
