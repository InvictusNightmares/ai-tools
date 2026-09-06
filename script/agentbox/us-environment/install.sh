#!/usr/bin/env bash
# Install on the existing, finalized Agentbox, from this repository directory.
set -Eeuo pipefail
[[ $(id -u) == 0 ]] || { echo 'root required' >&2; exit 1; }
source_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
[[ -s /etc/agentbox-profile/profiles.yaml && -s /srv/agentbox/headless-chrome/compose.yaml ]]
command -v nft >/dev/null
[[ -c /dev/net/tun ]]
[[ ! -e /etc/systemd/system/agentbox-us-egress.service ]] || { echo 'US policy is already installed; use the proxy updater instead.' >&2; exit 1; }
backup=/root/agentbox-us-backup
[[ ! -e $backup ]] || { echo 'An unfinished US environment backup exists; inspect it before continuing.' >&2; exit 1; }
timer_was_active=0
systemctl is-active --quiet agentbox-proxy-update.timer && timer_was_active=1
restore_schedule() {
  if [[ $timer_was_active == 1 ]]; then systemctl start agentbox-proxy-update.timer; fi
}
trap restore_schedule EXIT
systemctl stop agentbox-proxy-update.timer
exec 9>/run/lock/agentbox-proxy-update.lock
flock -w 60 9
install -d -m 700 "$backup" /srv/agentbox/us-environment
# Exact rollback inputs; this directory is removed after runtime acceptance.
tar -C / -cpf "$backup/before.tar" \
  etc/mihomo/config.yaml etc/mihomo-bootstrap/config.yaml etc/dhcpcd.conf etc/resolv.conf \
  etc/docker/daemon.json etc/agentbox-profile \
  usr/local/libexec/agentbox-profile-compiler.js usr/local/sbin/update-agentbox-proxy \
  srv/agentbox/headless-chrome/compose.yaml
cat >"$backup/rollback.sh" <<'EOF'
#!/bin/bash
set -e
systemctl disable --now agentbox-us-egress.service 2>/dev/null || true
rm -f /etc/systemd/system/agentbox-us-egress.service /usr/local/sbin/agentbox-us-egress
rm -f /srv/agentbox/us-environment/egress.nft
nft delete table inet agentbox_us 2>/dev/null || true
rm -f /etc/systemd/system/mihomo.service.d/us-environment.conf
rm -f /etc/systemd/system/docker.service.d/us-environment.conf /usr/local/sbin/agentbox-us-container-egress
rm -f /etc/agentbox-profile/agentbox-policy.yaml
# Restore only the recorded files, including the original private profile.
tar -C / -xpf /root/agentbox-us-backup/before.tar
tailscale set --accept-dns=true
systemctl daemon-reload
systemctl restart mihomo-bootstrap mihomo
systemctl restart docker
docker compose --env-file /srv/agentbox/headless-chrome/.env -f /srv/agentbox/headless-chrome/compose.yaml up -d
EOF
chmod 700 "$backup/rollback.sh"
trap 'echo "US installation failed; restoring recorded settings" >&2; bash "$backup/rollback.sh"; exit 1' ERR
install -m 0644 "$source_dir/us-environment/Dockerfile" /srv/agentbox/us-environment/Dockerfile
docker build --network=none -t agentbox-chrome-us:v2.56.2-1 /srv/agentbox/us-environment
install -m 0755 "$source_dir/agentbox-profile-compiler.js" /usr/local/libexec/agentbox-profile-compiler.js
install -m 0755 "$source_dir/update-agentbox-proxy.sh" /usr/local/sbin/update-agentbox-proxy
install -m 0755 "$source_dir/us-environment/check-dns.py" /usr/local/libexec/agentbox-check-dns.py
cat >/etc/agentbox-profile/agentbox-policy.yaml <<'EOF'
environment: us
proxy-server: 179.253.245.229
tailnet-domain: tailb6a44b.ts.net
EOF
chmod 600 /etc/agentbox-profile/agentbox-policy.yaml
# The rescue proxy resolves through its own tunnel, independent of production DNS.
node <<'JS'
const fs=require('fs'),y=require('/usr/local/libexec/vendor/js-yaml.cjs');
const f='/etc/mihomo-bootstrap/config.yaml',c=y.load(fs.readFileSync(f,'utf8'));
if (!c.proxies.every(p=>p.server==='179.253.245.229')) throw Error('Unexpected rescue node address');
c.dns={enable:true,ipv6:false,'enhanced-mode':'redir-host','default-nameserver':['1.1.1.1'],
  nameserver:['https://1.1.1.1/dns-query#BOOTSTRAP','https://8.8.8.8/dns-query#BOOTSTRAP','tls://9.9.9.9#BOOTSTRAP']};
fs.writeFileSync(f,y.dump(c));
JS
runuser -u mihomo -- /usr/local/bin/mihomo -t -d /var/lib/mihomo-bootstrap -f /etc/mihomo-bootstrap/config.yaml >/dev/null
systemctl restart mihomo-bootstrap
install -d -m 755 /etc/systemd/system/mihomo.service.d
cat >/etc/systemd/system/mihomo.service.d/us-environment.conf <<'EOF'
[Service]
PrivateDevices=false
DevicePolicy=closed
DeviceAllow=/dev/net/tun rw
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
RestrictAddressFamilies=
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK
EOF
systemctl daemon-reload
ufw allow in on ab-egress0 to 172.18.0.1 port 53 proto udp comment 'Agentbox container US DNS'
ufw allow in on ab-egress0 to 172.18.0.1 port 53 proto tcp comment 'Agentbox container US DNS'
# Needed for TCP/UDP packets delivered from the host TUN, not a public port.
ufw allow in on ab-us comment 'Agentbox US TUN responses'
flock -u 9
/usr/local/sbin/update-agentbox-proxy --force
flock -w 60 9
python3 /usr/local/libexec/agentbox-check-dns.py 127.0.0.1 53 github.com
python3 /usr/local/libexec/agentbox-check-dns.py 127.0.0.1 53 agentbox.tailb6a44b.ts.net
ip link show ab-us >/dev/null
tailscale set --accept-dns=false
if ! grep -qxF 'nohook resolv.conf' /etc/dhcpcd.conf; then
  printf '\n# Agentbox manages DNS through the US proxy.\nnohook resolv.conf\n' >> /etc/dhcpcd.conf
fi
cat >/etc/resolv.conf <<'EOF'
# Agentbox US DNS; DHCP and Tailscale must not overwrite this file.
nameserver 127.0.0.1
search tailb6a44b.ts.net
options timeout:3 attempts:2
EOF
# This gate stays in place if the production TUN exits: normal public traffic
# cannot silently fall back to the physical China interface. Preserve DHCP,
# local management, the DMIT tunnel, and Tailscale's own marked transport.
cat >/srv/agentbox/us-environment/egress.nft <<'EOF'
table inet agentbox_us {
 chain forward {
  type filter hook forward priority -10; policy accept;
  oifname "ens3" reject
 }
 chain output {
  type filter hook output priority -10; policy accept;
  oifname != "ens3" return
  meta l4proto { tcp, udp } th dport { 53, 853 } reject
  meta mark & 0xff0000 == 0x80000 return
  ip daddr 179.253.245.229 return
  udp sport 68 udp dport 67 return
  ip daddr { 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16 } return
  ip6 daddr fe80::/10 return
  meta l4proto ipv6-icmp return
  reject
 }
}
EOF
cat >/usr/local/sbin/agentbox-us-egress <<'EOF'
#!/bin/bash
set -e
# An atomic nft transaction replaces only this managed table.
if nft list table inet agentbox_us >/dev/null 2>&1; then
  { echo 'delete table inet agentbox_us'; cat /srv/agentbox/us-environment/egress.nft; } | nft -f -
else
  nft -f /srv/agentbox/us-environment/egress.nft
fi
EOF
chmod 755 /usr/local/sbin/agentbox-us-egress
cat >/etc/systemd/system/agentbox-us-egress.service <<'EOF'
[Unit]
Description=Prevent public traffic and plaintext DNS escaping the US tunnel
Before=mihomo.service
After=network-pre.target
Wants=network-pre.target
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/agentbox-us-egress
RemainAfterExit=true
[Install]
WantedBy=multi-user.target
EOF
nft -c -f /srv/agentbox/us-environment/egress.nft
systemctl daemon-reload
systemctl enable --now agentbox-us-egress
node <<'JS'
const fs=require('fs'),y=require('/usr/local/libexec/vendor/js-yaml.cjs');
const f='/srv/agentbox/headless-chrome/compose.yaml',c=y.load(fs.readFileSync(f,'utf8'));
c.services['headless-chrome'].image='agentbox-chrome-us:v2.56.2-1';
c.services['headless-chrome'].dns=['172.18.0.1'];
fs.writeFileSync(f,y.dump(c,{lineWidth:120}));
const d='/etc/docker/daemon.json',dc=JSON.parse(fs.readFileSync(d,'utf8'));
dc.dns=['172.18.0.1'];fs.writeFileSync(d,JSON.stringify(dc,null,2)+'\n');
JS
install -m 0755 "$source_dir/us-environment/container-egress.sh" /usr/local/sbin/agentbox-us-container-egress
install -m 0644 "$source_dir/us-environment/README.md" /srv/agentbox/us-environment/README.md
cat >/etc/systemd/system/docker.service.d/us-environment.conf <<'EOF'
[Service]
ExecStartPost=/usr/local/sbin/agentbox-us-container-egress
EOF
systemctl daemon-reload
systemctl restart docker
docker compose --env-file /srv/agentbox/headless-chrome/.env -f /srv/agentbox/headless-chrome/compose.yaml up -d
for _ in {1..40}; do
  [[ $(docker inspect -f '{{.State.Health.Status}}' agentbox-headless-chrome) == healthy ]] && break
  sleep 2
done
[[ $(docker inspect -f '{{.State.Health.Status}}' agentbox-headless-chrome) == healthy ]]
python3 /usr/local/libexec/agentbox-check-dns.py 127.0.0.1 53
curl --noproxy '*' --fail --silent --show-error --max-time 30 https://www.cloudflare.com/cdn-cgi/trace | grep -E '^(ip|loc|colo)='
docker exec agentbox-headless-chrome cat /etc/resolv.conf
printf 'US_ENVIRONMENT_INSTALLED\n'
trap - ERR
