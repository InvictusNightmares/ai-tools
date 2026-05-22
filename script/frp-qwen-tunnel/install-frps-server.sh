#!/usr/bin/env bash
set -euo pipefail

FRP_VERSION="${FRP_VERSION:-0.61.1}"
FRP_DIR="${FRP_DIR:-/opt/frp}"
FRPS_BIND_PORT="${FRPS_BIND_PORT:-7000}"
FRPS_PROXY_BIND_ADDR="${FRPS_PROXY_BIND_ADDR:-127.0.0.1}"
FRP_TOKEN="${FRP_TOKEN:-}"
SERVICE_NAME="${SERVICE_NAME:-frps-qwen}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

if [[ -z "${FRP_TOKEN}" ]]; then
  if command -v openssl >/dev/null 2>&1; then
    FRP_TOKEN="$(openssl rand -hex 24)"
  else
    FRP_TOKEN="$(date +%s | sha256sum | awk '{print $1}')"
  fi
  echo "Generated FRP_TOKEN: ${FRP_TOKEN}"
  echo "Save this token and use the same value on the GPU frpc client."
fi

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

mkdir -p "${FRP_DIR}"
curl -fsSL "${url}" -o "${tmp_dir}/${archive}"
tar -xzf "${tmp_dir}/${archive}" -C "${tmp_dir}"
install -m 0755 "${tmp_dir}/frp_${FRP_VERSION}_linux_${frp_arch}/frps" "${FRP_DIR}/frps"

cat > "${FRP_DIR}/frps.toml" <<EOF
bindPort = ${FRPS_BIND_PORT}
proxyBindAddr = "${FRPS_PROXY_BIND_ADDR}"

auth.method = "token"
auth.token = "${FRP_TOKEN}"
EOF

chmod 600 "${FRP_DIR}/frps.toml"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=FRP server for Qwen tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=${FRP_DIR}/frps -c ${FRP_DIR}/frps.toml
Restart=always
RestartSec=5
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.service"

echo "frps installed."
echo "Service: ${SERVICE_NAME}.service"
echo "Control port: ${FRPS_BIND_PORT}"
echo "Remote proxies will bind to: ${FRPS_PROXY_BIND_ADDR}"
echo "Verify: systemctl status ${SERVICE_NAME}.service"
