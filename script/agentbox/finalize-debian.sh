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
if ! systemctl is-active --quiet mihomo; then
  echo "Mihomo is not active; refusing to harden the only remote path." >&2
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
systemctl enable ssh tailscaled mihomo fstrim.timer

echo
echo "Root password is locked and SSH hardening is complete."
echo "Revoke the one-time auth key in the Tailscale admin console, then reboot and test again."
