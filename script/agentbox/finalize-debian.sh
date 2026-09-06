#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $(id -u) -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

if [[ ! -s /root/.ssh/authorized_keys ]]; then
  echo "root has no authorized_keys; refusing to harden SSH." >&2
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

if ! iptables -C DOCKER-USER -j AGENTBOX-DOCKER >/dev/null 2>&1; then
  echo "The Docker ingress guard is missing; refusing to finalize the host." >&2
  exit 1
fi
if ! docker network inspect agentbox-browser >/dev/null 2>&1 || \
   [[ $(docker inspect --format '{{.State.Health.Status}}' agentbox-headless-chrome 2>/dev/null) != healthy ]]; then
  echo "The internal Headless Chrome service is not healthy; refusing to finalize the host." >&2
  exit 1
fi

# OpenSSH uses the first value it reads. The installer leaves a
# 01-permitrootlogin.conf file, so the managed policy must load before it.
cat >/etc/ssh/sshd_config.d/00-agentbox.conf <<'EOF'
PermitRootLogin prohibit-password
AuthenticationMethods publickey
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
AllowUsers root
X11Forwarding no
ClientAliveInterval 120
ClientAliveCountMax 3
EOF

# Remove the managed file used by older Agentbox bootstrap versions.
rm -f /etc/ssh/sshd_config.d/90-agentbox.conf
sshd -t
effective_ssh_config=$(sshd -T)
for setting in \
  'permitrootlogin without-password' \
  'authenticationmethods publickey' \
  'passwordauthentication no' \
  'kbdinteractiveauthentication no' \
  'pubkeyauthentication yes' \
  'allowusers root'; do
  if ! grep -Fqx "$setting" <<<"$effective_ssh_config"; then
    echo "The effective SSH configuration does not enforce: $setting" >&2
    exit 1
  fi
done
unset effective_ssh_config setting
systemctl reload ssh

echo
echo "The hardened SSH configuration is active, but the current session remains open."
echo "Keep this session open. From a second terminal on the physical PC, verify:"
echo "  ssh -i ~/.ssh/agentbox_ed25519 root@agentbox"
echo "  id -u  # must print 0"
echo
read -r -p "After the second root SSH test succeeds, type LOCK ROOT PASSWORD: " confirmation
if [[ $confirmation != 'LOCK ROOT PASSWORD' ]]; then
  echo "Root password remains unlocked. Re-run this script after fixing remote access." >&2
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
echo "Root password is locked; root public-key SSH remains enabled."
echo "Revoke the one-time auth key in the Tailscale admin console, then reboot and test again."
