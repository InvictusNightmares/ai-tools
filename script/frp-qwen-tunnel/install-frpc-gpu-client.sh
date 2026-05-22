#!/usr/bin/env bash
set -euo pipefail

FRP_VERSION="${FRP_VERSION:-0.61.2}"
FRP_DIR="${FRP_DIR:-/opt/frp}"
FRPC_BIN="${FRPC_BIN:-/usr/local/bin/frpc}"
FRPS_SERVER_ADDR="${FRPS_SERVER_ADDR:-}"
FRPS_SERVER_PORT="${FRPS_SERVER_PORT:-7000}"
FRP_TOKEN="${FRP_TOKEN:-}"
LOCAL_IP="${LOCAL_IP:-127.0.0.1}"
LOCAL_PORT="${LOCAL_PORT:-8000}"
REMOTE_PORT="${REMOTE_PORT:-18000}"
PROXY_NAME="${PROXY_NAME:-qwen-vllm}"
SERVICE_NAME="${SERVICE_NAME:-frpc-qwen-singapore}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

if [[ -z "${FRPS_SERVER_ADDR}" ]]; then
  echo "FRPS_SERVER_ADDR is required, e.g. FRPS_SERVER_ADDR=1.2.3.4" >&2
  exit 1
fi

if [[ -z "${FRP_TOKEN}" ]]; then
  echo "FRP_TOKEN is required. Use the token from the frps server install." >&2
  exit 1
fi

mkdir -p "${FRP_DIR}"

if [[ -x "${FRPC_BIN}" ]]; then
  echo "Using existing frpc: ${FRPC_BIN} ($(${FRPC_BIN} --version 2>/dev/null || true))"
elif command -v frpc >/dev/null 2>&1; then
  FRPC_BIN="$(command -v frpc)"
  echo "Using existing frpc from PATH: ${FRPC_BIN} ($(${FRPC_BIN} --version 2>/dev/null || true))"
else
  echo "frpc not found. Installing frpc ${FRP_VERSION} to ${FRPC_BIN}."

  arch="$(uname -m)"
  case "${arch}" in
    x86_64|amd64) frp_arch="amd64" ;;
    aarch64|arm64) frp_arch="arm64" ;;
    *) echo "Unsupported architecture: ${arch}" >&2; exit 1 ;;
  esac

  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir}"' EXIT

  archive="frp_${FRP_VERSION}_linux_${frp_arch}.tar.gz"
  url="https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/${archive}"

  curl -fsSL "${url}" -o "${tmp_dir}/${archive}"
  tar -xzf "${tmp_dir}/${archive}" -C "${tmp_dir}"
  install -m 0755 "${tmp_dir}/frp_${FRP_VERSION}_linux_${frp_arch}/frpc" "${FRPC_BIN}"
fi

cat > "${FRP_DIR}/${SERVICE_NAME}.toml" <<EOF
serverAddr = "${FRPS_SERVER_ADDR}"
serverPort = ${FRPS_SERVER_PORT}

auth.method = "token"
auth.token = "${FRP_TOKEN}"
transport.tcpMux = true
log.to = "/var/log/${SERVICE_NAME}.log"
log.level = "info"

[[proxies]]
name = "${PROXY_NAME}"
type = "tcp"
localIP = "${LOCAL_IP}"
localPort = ${LOCAL_PORT}
remotePort = ${REMOTE_PORT}
EOF

chmod 600 "${FRP_DIR}/${SERVICE_NAME}.toml"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=FRP client for Qwen vLLM tunnel to ${FRPS_SERVER_ADDR}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=${FRPC_BIN} -c ${FRP_DIR}/${SERVICE_NAME}.toml
Restart=always
RestartSec=5
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.service"

echo "frpc client service installed."
echo "Binary: ${FRPC_BIN}"
echo "Service: ${SERVICE_NAME}.service"
echo "Tunnel: ${FRPS_SERVER_ADDR}:127.0.0.1:${REMOTE_PORT} -> ${LOCAL_IP}:${LOCAL_PORT} on this GPU host"
echo "Verify on GPU: systemctl status ${SERVICE_NAME}.service"
echo "Verify on server: curl http://127.0.0.1:${REMOTE_PORT}/v1/models"
