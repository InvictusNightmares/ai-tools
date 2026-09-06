#!/usr/bin/env bash
# Opt-in migration for a single-user host: root SSH with public keys only.
# Keep agent access until a separate, fresh root connection has been verified.
set -Eeuo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
[[ $# == 1 && -f $1 && ! -L $1 ]] || { echo 'Pass one public-key file.' >&2; exit 1; }
[[ $(awk 'NF {n++} END {print n+0}' "$1") == 1 ]] || { echo 'Expected one public key.' >&2; exit 1; }
ssh-keygen -lf "$1" >/dev/null
read -r key_type key_data _ <"$1"
[[ $key_type == ssh-ed25519 && -n $key_data ]] || { echo 'Expected an Ed25519 public key.' >&2; exit 1; }
key_line="$key_type $key_data agentbox-admin"
policy=/etc/ssh/sshd_config.d/00-agentbox.conf
keys=/root/.ssh/authorized_keys
[[ -f $policy && ! -L $policy && ! -L /root/.ssh && ! -L $keys ]] || { echo 'Unexpected managed SSH paths.' >&2; exit 1; }
/usr/sbin/sshd -t
umask 077
backup=$(mktemp -d /run/agentbox-root-ssh.XXXXXXXX)
cp -a "$policy" "$backup/policy"
if [[ -e $keys ]]; then cp -a "$keys" "$backup/authorized_keys"; fi
rollback() {
  status=$?
  trap - EXIT
  if (( status != 0 )); then
    cp -a "$backup/policy" "$policy"
    if [[ -e $backup/authorized_keys ]]; then
      cp -a "$backup/authorized_keys" "$keys"
    else
      rm -f "$keys"
    fi
    /usr/sbin/sshd -t && systemctl reload ssh
    echo "Migration failed; previous SSH files restored. Backup: $backup" >&2
  fi
  exit "$status"
}
trap rollback EXIT
install -d -m 700 -o root -g root /root/.ssh
touch "$keys"
if ! awk -v t="$key_type" -v k="$key_data" '$1==t && $2==k {found=1} END {exit !found}' "$keys"; then
  printf '\n%s\n' "$key_line" >>"$keys"
fi
chown root:root "$keys"
chmod 600 "$keys"
cat >"$policy" <<'EOF'
PermitRootLogin prohibit-password
AuthenticationMethods publickey
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
AllowUsers root agent
X11Forwarding no
ClientAliveInterval 120
ClientAliveCountMax 3
EOF
chown root:root "$policy"
chmod 644 "$policy"
/usr/sbin/sshd -t
for user in root agent; do
  effective=$(/usr/sbin/sshd -T -C "user=$user,host=agentbox,addr=100.66.88.36")
  for setting in \
    'authenticationmethods publickey' 'passwordauthentication no' \
    'kbdinteractiveauthentication no' 'pubkeyauthentication yes' \
    'permitemptypasswords no'; do
    grep -Fxq "$setting" <<<"$effective" || { echo "Effective SSH policy mismatch: $setting" >&2; exit 1; }
  done
  allowed=$(awk '$1 == "allowusers" {for (i=2;i<=NF;i++) print $i}' <<<"$effective" | LC_ALL=C sort -u)
  [[ $allowed == $'agent\nroot' ]] || { echo 'Unexpected effective AllowUsers.' >&2; exit 1; }
  grep -Eq '^permitrootlogin (prohibit-password|without-password)$' <<<"$effective"
done
systemctl reload ssh
trap - EXIT
echo 'ROOT_KEY_SSH_READY: verify a new root SSH connection before retiring agent.'
echo "Rollback backup: $backup"
