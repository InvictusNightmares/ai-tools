#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $(id -u) -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

if [[ ! -s /home/agent/.ssh/authorized_keys ]]; then
  echo "agent has no authorized_keys; refusing to harden SSH." >&2
  exit 1
fi
if ! systemctl is-active --quiet mihomo-bootstrap.service; then
  echo "The bootstrap Mihomo service is not active; refusing to harden the remote path." >&2
  exit 1
fi
if ! tailscale status >/dev/null 2>&1; then
  echo "Tailscale is not connected; refusing to harden SSH." >&2
  exit 1
fi
if ! ufw status | grep -Fq 'Status: active'; then
  echo "UFW is not active; refusing to harden SSH." >&2
  exit 1
fi
if ! systemctl is-active --quiet docker.service || \
   ! systemctl is-active --quiet agentbox-container-proxy.service || \
   ! docker network inspect agentbox-egress >/dev/null 2>&1 || \
   ! docker compose version >/dev/null 2>&1; then
  echo "The Docker application platform is incomplete; refusing to finalize the host." >&2
  exit 1
fi
if id -nG agent | tr ' ' '\n' | grep -qx docker; then
  echo "The agent user has root-equivalent docker group access; refusing to finalize the host." >&2
  exit 1
fi
if ! iptables -C DOCKER-USER -j AGENTBOX-DOCKER >/dev/null 2>&1; then
  echo "The Docker ingress guard is missing; refusing to finalize the host." >&2
  exit 1
fi
if ! docker network inspect agentbox-browser >/dev/null 2>&1 || \
   [[ $(docker inspect --format '{{.State.Health.Status}}' agentbox-headless-chrome 2>/dev/null) != healthy ]]; then
  echo "The internal Headless Chrome service is not healthy; refusing to finalize the host." >&2
  exit 1
fi

cat >/etc/ssh/sshd_config.d/90-agentbox.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
AllowUsers agent
X11Forwarding no
ClientAliveInterval 120
ClientAliveCountMax 3
EOF

sshd -t
systemctl reload ssh

echo
echo "The hardened SSH configuration is active, but the current session remains open."
echo "Keep this session open. From a second terminal on the physical PC, verify:"
echo "  ssh -i ~/.ssh/agentbox_ed25519 agent@agentbox"
echo "  sudo -v"
echo
read -r -p "After the second SSH and sudo test succeeds, type LOCK ROOT: " confirmation
if [[ $confirmation != 'LOCK ROOT' ]]; then
  echo "Root remains unlocked. Re-run this script after fixing remote access." >&2
  exit 1
fi

passwd -l root
systemctl enable \
  ssh \
  tailscaled \
  mihomo-bootstrap.service \
  mihomo.service \
  docker.service \
  containerd.service \
  agentbox-container-proxy.service \
  fstrim.timer
if systemctl is-active --quiet mihomo.service; then
  systemctl enable agentbox-proxy-update.timer
fi

echo
echo "Root password is locked and SSH hardening is complete."
echo "Revoke the one-time auth key in the Tailscale admin console, then reboot and test again."
