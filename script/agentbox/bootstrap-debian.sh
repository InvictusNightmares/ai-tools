#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $(id -u) -ne 0 ]]; then
  echo "Run this script as root from the Tianyi console." >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "/etc/os-release is missing." >&2
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
if [[ ${ID:-} != debian || ${VERSION_ID:-} != 13* ]]; then
  echo "Expected Debian 13; found ID=${ID:-unknown} VERSION_ID=${VERSION_ID:-unknown}." >&2
  exit 1
fi

if [[ ! -s /etc/mihomo/config.yaml || ! -x /usr/local/bin/mihomo ]]; then
  echo "The private Mihomo bootstrap was not installed by the Debian installer." >&2
  exit 1
fi

systemctl daemon-reload
systemctl enable --now mihomo
if ! systemctl is-active --quiet mihomo; then
  journalctl -u mihomo --no-pager -n 100 >&2
  exit 1
fi

export http_proxy=http://127.0.0.1:7897
export https_proxy=http://127.0.0.1:7897
export HTTP_PROXY=$http_proxy
export HTTPS_PROXY=$https_proxy

read -r -p "Paste the physical PC's Ed25519 SSH public key: " ssh_public_key
if [[ ! $ssh_public_key =~ ^ssh-ed25519\ [A-Za-z0-9+/=]+([[:space:]].*)?$ ]]; then
  echo "The supplied value is not an ssh-ed25519 public key." >&2
  exit 1
fi

hostnamectl set-hostname agentbox
timedatectl set-timezone Asia/Shanghai
if grep -qE '^127\.0\.1\.1[[:space:]]' /etc/hosts; then
  sed -i -E 's/^127\.0\.1\.1[[:space:]].*/127.0.1.1 agentbox/' /etc/hosts
else
  printf '\n127.0.1.1 agentbox\n' >>/etc/hosts
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get full-upgrade -y
apt-get install -y \
  apt-listchanges \
  ca-certificates \
  curl \
  git \
  gnupg \
  openssh-server \
  sudo \
  ufw \
  unattended-upgrades

if ! id agent >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash agent
fi
usermod -aG sudo agent

echo "Set the local password for agent. It is used for console login and sudo, not SSH."
passwd agent

install -d -m 0700 -o agent -g agent /home/agent/.ssh
printf '%s\n' "$ssh_public_key" >/home/agent/.ssh/authorized_keys
chown agent:agent /home/agent/.ssh/authorized_keys
chmod 0600 /home/agent/.ssh/authorized_keys
unset ssh_public_key

if ! swapon --show=NAME --noheadings | grep -qx '/swapfile'; then
  if [[ ! -e /swapfile ]]; then
    if ! fallocate -l 4G /swapfile; then
      dd if=/dev/zero of=/swapfile bs=1M count=4096 status=progress
    fi
    chmod 0600 /swapfile
    mkswap /swapfile
  fi
  swapon /swapfile
fi
if ! grep -qE '^/swapfile[[:space:]]' /etc/fstab; then
  printf '/swapfile none swap sw 0 0\n' >>/etc/fstab
fi
printf 'vm.swappiness=10\n' >/etc/sysctl.d/90-agentbox-swap.conf
sysctl --system >/dev/null

cat >/etc/apt/apt.conf.d/52agentbox-unattended-local <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

install -d -m 0755 /usr/share/keyrings
curl -fsSL \
  -o /usr/share/keyrings/tailscale-archive-keyring.gpg \
  https://pkgs.tailscale.com/stable/debian/trixie.noarmor.gpg
curl -fsSL \
  -o /etc/apt/sources.list.d/tailscale.list \
  https://pkgs.tailscale.com/stable/debian/trixie.tailscale-keyring.list
apt-get update
apt-get install -y tailscale

install -d -m 0755 /etc/systemd/system/tailscaled.service.d
cat >/etc/systemd/system/tailscaled.service.d/proxy.conf <<'EOF'
[Unit]
Wants=mihomo.service
After=mihomo.service

[Service]
Environment=HTTP_PROXY=http://127.0.0.1:7897
Environment=HTTPS_PROXY=http://127.0.0.1:7897
EOF

systemctl daemon-reload
systemctl enable --now ssh
systemctl enable --now tailscaled
systemctl enable --now fstrim.timer

read -r -s -p "Paste the one-time tagged Tailscale auth key: " tailscale_auth_key
echo
if [[ $tailscale_auth_key != tskey-* ]]; then
  unset tailscale_auth_key
  echo "The value does not look like a Tailscale auth key." >&2
  exit 1
fi
tailscale up \
  --auth-key="$tailscale_auth_key" \
  --hostname=agentbox \
  --advertise-tags=tag:agent-server
unset tailscale_auth_key

ufw default deny incoming
ufw default allow outgoing
if ! ufw status | grep -Fq '22/tcp on tailscale0'; then
  ufw allow in on tailscale0 to any port 22 proto tcp comment 'OpenSSH over Tailscale'
fi
ufw --force enable

echo
echo "Bootstrap completed. Root is intentionally not locked yet."
echo "From the physical PC, test: ssh -i ~/.ssh/agentbox_ed25519 agent@agentbox"
echo "Then test sudo -v and run finalize-debian.sh from that SSH session."
