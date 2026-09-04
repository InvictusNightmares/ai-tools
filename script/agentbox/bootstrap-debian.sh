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

if [[ ! -s /etc/mihomo-bootstrap/config.yaml || ! -s /etc/mihomo/config.yaml || \
      ! -x /usr/local/bin/mihomo || ! -x /usr/local/libexec/agentbox-profile-compiler.js ]]; then
  echo "The private dual-proxy bundle was not installed by the Debian installer." >&2
  exit 1
fi

systemctl daemon-reload
systemctl enable --now mihomo-bootstrap.service mihomo.service
if ! systemctl is-active --quiet mihomo-bootstrap.service; then
  journalctl -u mihomo-bootstrap.service --no-pager -n 100 >&2
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
timedatectl set-timezone America/Los_Angeles
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
  locales \
  nodejs \
  openssl \
  openssh-server \
  socat \
  sudo \
  ufw \
  unattended-upgrades \
  util-linux

english_only_incompatible_packages=(
  locales-all
  task-chinese
  task-chinese-desktop
  fonts-arphic-bkai00mp
  fonts-arphic-bsmi00lp
  fonts-arphic-gbsn00lp
  fonts-arphic-gkai00mp
  fonts-arphic-ukai
  fonts-arphic-uming
  fonts-wqy-microhei
  fonts-wqy-zenhei
  ibus-chewing
  ibus-libpinyin
  ibus-pinyin
  ibus-rime
  fcitx-chewing
  fcitx-googlepinyin
  fcitx-libpinyin
  fcitx-pinyin
  fcitx-rime
  fcitx5-chewing
  fcitx5-chinese-addons
  fcitx5-rime
  zhcon
)
installed_incompatible_packages=()
for package in "${english_only_incompatible_packages[@]}"; do
  if dpkg-query -W -f='${db:Status-Status}\n' "$package" 2>/dev/null | grep -qx installed; then
    installed_incompatible_packages+=("$package")
  fi
done
if [[ ${#installed_incompatible_packages[@]} -gt 0 ]]; then
  apt-get purge -y "${installed_incompatible_packages[@]}"
fi

printf 'en_US.UTF-8 UTF-8\n' >/etc/locale.gen
locale-gen
update-locale --reset LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export LANGUAGE=en_US:en
export LC_ALL=en_US.UTF-8

if [[ $(timedatectl show --property=Timezone --value) != America/Los_Angeles ]]; then
  echo "Failed to set the system timezone to America/Los_Angeles." >&2
  exit 1
fi
if ! locale -a | grep -qx 'en_US.utf8' || locale -a | grep -Eiq '^zh([_.]|$)'; then
  echo "The generated locale set is not English-only." >&2
  exit 1
fi

node /usr/local/libexec/agentbox-profile-compiler.js --self-test

production_ready=0
if systemctl is-active --quiet mihomo.service && \
    curl --silent --show-error --fail --head \
      --connect-timeout 5 --max-time 20 \
      --proxy http://127.0.0.1:7898 \
      https://github.com/ >/dev/null 2>&1; then
  production_ready=1
  cat >/etc/apt/apt.conf.d/80agentbox-proxy <<'EOF'
Acquire::http::Proxy "http://127.0.0.1:7898/";
Acquire::https::Proxy "http://127.0.0.1:7898/";
EOF
  cat >/etc/profile.d/agentbox-proxy.sh <<'EOF'
export http_proxy=http://127.0.0.1:7898
export https_proxy=http://127.0.0.1:7898
export HTTP_PROXY=http://127.0.0.1:7898
export HTTPS_PROXY=http://127.0.0.1:7898
EOF
  install -d -o root -g root -m 0700 /var/lib/agentbox-profile
  touch /var/lib/agentbox-profile/last-success
  chmod 0600 /var/lib/agentbox-profile/last-success
else
  echo "WARNING: the production rules proxy on 127.0.0.1:7898 failed its HTTPS health check." >&2
  echo "The bootstrap proxy and Tailscale path will remain independent on 127.0.0.1:7897." >&2
fi

docker_conflicting_packages=(
  containerd
  docker-buildx
  docker-compose
  docker-doc
  docker.io
  podman-docker
  runc
)
installed_docker_conflicts=()
for package in "${docker_conflicting_packages[@]}"; do
  if dpkg-query -W -f='${db:Status-Status}\n' "$package" 2>/dev/null | grep -qx installed; then
    installed_docker_conflicts+=("$package")
  fi
done
if [[ ${#installed_docker_conflicts[@]} -gt 0 ]]; then
  apt-get remove -y "${installed_docker_conflicts[@]}"
fi

install -d -m 0755 /etc/apt/keyrings
curl -fsSL \
  -o /etc/apt/keyrings/docker.asc \
  https://download.docker.com/linux/debian/gpg
chmod a+r /etc/apt/keyrings/docker.asc
docker_architecture=$(dpkg --print-architecture)
cat >/etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: trixie
Components: stable
Architectures: $docker_architecture
Signed-By: /etc/apt/keyrings/docker.asc
EOF
unset docker_architecture

apt-get update
apt-get install -y \
  containerd.io \
  docker-buildx-plugin \
  docker-ce \
  docker-ce-cli \
  docker-compose-plugin

if systemctl is-active --quiet docker.service && \
    [[ -n $(docker ps --all --quiet 2>/dev/null) ]]; then
  echo "Refusing to replace Docker's bootstrap configuration while containers exist." >&2
  exit 1
fi
systemctl stop docker.service docker.socket 2>/dev/null || true

install -d -m 0755 /etc/docker /etc/systemd/system/docker.service.d
cat >/etc/docker/daemon.json <<'EOF'
{
  "default-network-opts": {
    "bridge": {
      "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1"
    }
  },
  "live-restore": true,
  "log-driver": "local",
  "no-new-privileges": true,
  "proxies": {
    "http-proxy": "http://127.0.0.1:7897",
    "https-proxy": "http://127.0.0.1:7897",
    "no-proxy": "localhost,127.0.0.0/8,::1,.ts.net"
  }
}
EOF

cat >/usr/local/sbin/agentbox-docker-firewall <<'EOF'
#!/bin/sh
set -eu

configure_family() {
    firewall_command=$1
    if ! command -v "$firewall_command" >/dev/null 2>&1 || \
       ! "$firewall_command" -w -n -L DOCKER-USER >/dev/null 2>&1; then
        return
    fi

    "$firewall_command" -w -N AGENTBOX-DOCKER 2>/dev/null || true
    "$firewall_command" -w -F AGENTBOX-DOCKER
    "$firewall_command" -w -A AGENTBOX-DOCKER -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    "$firewall_command" -w -A AGENTBOX-DOCKER -i tailscale0 -j ACCEPT
    "$firewall_command" -w -A AGENTBOX-DOCKER -i docker0 -j ACCEPT
    "$firewall_command" -w -A AGENTBOX-DOCKER -i br+ -j ACCEPT
    "$firewall_command" -w -A AGENTBOX-DOCKER -j DROP

    while "$firewall_command" -w -C DOCKER-USER -j AGENTBOX-DOCKER >/dev/null 2>&1; do
        "$firewall_command" -w -D DOCKER-USER -j AGENTBOX-DOCKER
    done
    "$firewall_command" -w -I DOCKER-USER 1 -j AGENTBOX-DOCKER
}

configure_family iptables
configure_family ip6tables
EOF
chmod 0755 /usr/local/sbin/agentbox-docker-firewall

cat >/etc/systemd/system/docker.service.d/agentbox.conf <<'EOF'
[Unit]
Wants=mihomo-bootstrap.service
After=mihomo-bootstrap.service

[Service]
ExecStartPost=/usr/local/sbin/agentbox-docker-firewall
EOF

if ! id agent >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash agent
fi
usermod -aG sudo agent
install -d -m 0750 -o root -g agent /srv/agentbox

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
Wants=mihomo-bootstrap.service
After=mihomo-bootstrap.service

[Service]
Environment=HTTP_PROXY=http://127.0.0.1:7897
Environment=HTTPS_PROXY=http://127.0.0.1:7897
EOF

systemctl daemon-reload
systemctl enable --now ssh
systemctl enable --now tailscaled
systemctl enable --now fstrim.timer
if [[ $production_ready -eq 1 ]]; then
  systemctl enable --now agentbox-proxy-update.timer
else
  systemctl disable --now agentbox-proxy-update.timer 2>/dev/null || true
fi

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

systemctl enable --now containerd.service docker.service
if ! docker network inspect agentbox-egress >/dev/null 2>&1; then
  docker network create \
    --driver bridge \
    --opt com.docker.network.bridge.name=ab-egress0 \
    agentbox-egress >/dev/null
fi
container_proxy_gateway=$(docker network inspect \
  --format '{{(index .IPAM.Config 0).Gateway}}' agentbox-egress)
container_proxy_subnet=$(docker network inspect \
  --format '{{(index .IPAM.Config 0).Subnet}}' agentbox-egress)
if [[ ! $container_proxy_gateway =~ ^[0-9]+(\.[0-9]+){3}$ || \
      ! $container_proxy_subnet =~ ^[0-9]+(\.[0-9]+){3}/[0-9]+$ ]]; then
  echo "Docker did not assign the expected IPv4 egress network." >&2
  exit 1
fi

cat >/etc/default/agentbox-container-proxy <<EOF
PROXY_BIND_ADDRESS=$container_proxy_gateway
PROXY_TARGET_PORT=7898
EOF
chmod 0644 /etc/default/agentbox-container-proxy

cat >/usr/local/sbin/agentbox-container-proxy <<'EOF'
#!/bin/sh
set -eu

. /etc/default/agentbox-container-proxy
case ${PROXY_BIND_ADDRESS:-} in
    ''|*[!0-9.]*) exit 1 ;;
esac
case ${PROXY_TARGET_PORT:-} in
    ''|*[!0-9]*) exit 1 ;;
esac
exec /usr/bin/socat \
    "TCP4-LISTEN:7898,bind=$PROXY_BIND_ADDRESS,reuseaddr,fork" \
    "TCP4:127.0.0.1:$PROXY_TARGET_PORT"
EOF
chmod 0755 /usr/local/sbin/agentbox-container-proxy

cat >/etc/systemd/system/agentbox-container-proxy.service <<'EOF'
[Unit]
Description=Expose the production proxy only to the Agentbox Docker egress network
Wants=docker.service mihomo-bootstrap.service mihomo.service
After=docker.service mihomo-bootstrap.service mihomo.service

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=/usr/local/sbin/agentbox-container-proxy
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateDevices=true
PrivateTmp=true
ProtectClock=true
ProtectControlGroups=true
ProtectHome=true
ProtectHostname=true
ProtectKernelLogs=true
ProtectKernelModules=true
ProtectKernelTunables=true
ProtectSystem=strict
RestrictAddressFamilies=AF_INET
RestrictNamespaces=true
LockPersonality=true

[Install]
WantedBy=multi-user.target
EOF

cat >/srv/agentbox/proxy.env <<EOF
HTTP_PROXY=http://$container_proxy_gateway:7898
HTTPS_PROXY=http://$container_proxy_gateway:7898
NO_PROXY=localhost,127.0.0.1,::1,.ts.net,$container_proxy_subnet
http_proxy=http://$container_proxy_gateway:7898
https_proxy=http://$container_proxy_gateway:7898
no_proxy=localhost,127.0.0.1,::1,.ts.net,$container_proxy_subnet
EOF
chown root:agent /srv/agentbox/proxy.env
chmod 0640 /srv/agentbox/proxy.env

if ! ufw status | grep -Fq '7898/tcp on ab-egress0'; then
  ufw allow in on ab-egress0 to "$container_proxy_gateway" port 7898 proto tcp \
    comment 'Mihomo for Agentbox containers'
fi
/usr/local/sbin/agentbox-docker-firewall
systemctl daemon-reload
systemctl enable --now agentbox-container-proxy.service

if ! docker network inspect agentbox-browser >/dev/null 2>&1; then
  docker network create --driver bridge --internal agentbox-browser >/dev/null
fi
install -d -m 0750 -o root -g agent \
  /srv/agentbox/headless-chrome \
  /srv/agentbox/secrets
if [[ ! -s /srv/agentbox/secrets/browserless-token ]]; then
  openssl rand -hex 32 >/srv/agentbox/secrets/browserless-token
fi
chown root:agent /srv/agentbox/secrets/browserless-token
chmod 0640 /srv/agentbox/secrets/browserless-token
browserless_token=$(tr -d '\r\n' </srv/agentbox/secrets/browserless-token)
if [[ ! $browserless_token =~ ^[a-f0-9]{64}$ ]]; then
  echo "The Browserless authentication token is malformed." >&2
  exit 1
fi
printf 'BROWSERLESS_TOKEN=%s\n' "$browserless_token" \
  >/srv/agentbox/headless-chrome/.env
chown root:root /srv/agentbox/headless-chrome/.env
chmod 0600 /srv/agentbox/headless-chrome/.env

cat >/srv/agentbox/headless-chrome/client.env <<EOF
BROWSERLESS_BASE_URL=ws://headless-chrome:3000/chrome
BROWSERLESS_TOKEN=$browserless_token
BROWSERLESS_PROXY_SERVER=http://$container_proxy_gateway:7898
BROWSERLESS_LANGUAGE=en-US
EOF
chown root:agent /srv/agentbox/headless-chrome/client.env
chmod 0640 /srv/agentbox/headless-chrome/client.env
unset browserless_token

cat >/srv/agentbox/headless-chrome/compose.yaml <<'EOF'
name: agentbox-headless-chrome

services:
  headless-chrome:
    image: ghcr.io/browserless/chrome:v2.56.2@sha256:1be15d1e3bad53e89d07ef529a52615739f77b7cd997a49c0ec97aaa78d0fcaf
    container_name: agentbox-headless-chrome
    restart: unless-stopped
    init: true
    env_file:
      - /srv/agentbox/proxy.env
    environment:
      CONCURRENT: "2"
      HEALTH: "true"
      LANG: en_US.UTF-8
      LANGUAGE: en_US:en
      LC_ALL: en_US.UTF-8
      MAX_CPU_PERCENT: "85"
      MAX_MEMORY_PERCENT: "85"
      QUEUED: "10"
      TIMEOUT: "300000"
      TOKEN: "${BROWSERLESS_TOKEN}"
      TZ: America/Los_Angeles
    shm_size: 2gb
    mem_limit: 4g
    cpus: 4.0
    pids_limit: 512
    security_opt:
      - no-new-privileges:true
    healthcheck:
      test:
        - CMD-SHELL
        - >-
          node -e "fetch('http://127.0.0.1:3000/pressure?token='+encodeURIComponent(process.env.TOKEN)).then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    networks:
      - agentbox-browser
      - agentbox-egress

networks:
  agentbox-browser:
    external: true
  agentbox-egress:
    external: true
EOF
chown root:agent \
  /srv/agentbox/headless-chrome/client.env \
  /srv/agentbox/headless-chrome/compose.yaml
chmod 0640 /srv/agentbox/headless-chrome/client.env
chmod 0644 /srv/agentbox/headless-chrome/compose.yaml

docker compose \
  --env-file /srv/agentbox/headless-chrome/.env \
  --file /srv/agentbox/headless-chrome/compose.yaml \
  up --detach --wait --wait-timeout 180

docker version >/dev/null
docker compose version >/dev/null
docker run --rm hello-world >/dev/null
if [[ $(docker inspect --format '{{.State.Health.Status}}' agentbox-headless-chrome) != healthy ]]; then
  echo "The Headless Chrome service did not become healthy." >&2
  exit 1
fi
if id -nG agent | tr ' ' '\n' | grep -qx docker; then
  echo "The agent user must not belong to the root-equivalent docker group." >&2
  exit 1
fi
unset container_proxy_gateway container_proxy_subnet

echo
echo "Bootstrap completed. Root is intentionally not locked yet."
if [[ $production_ready -eq 1 ]]; then
  echo "Daily APT/shell traffic uses the full imported rules on 127.0.0.1:7898."
  echo "Tailscale remains on the independent bootstrap proxy at 127.0.0.1:7897."
else
  echo "Daily traffic temporarily remains on 127.0.0.1:7897; diagnose mihomo.service before enabling the update timer."
fi
echo "Docker Engine, Buildx, and Compose are ready; manage workloads with sudo docker."
echo "Application stacks belong under /srv/agentbox and must attach to agentbox-egress when using /srv/agentbox/proxy.env."
echo "Headless Chrome is healthy, English-only at runtime, and internal to agentbox-browser; its token was not printed."
echo "From the physical PC, test: ssh -i ~/.ssh/agentbox_ed25519 agent@agentbox"
echo "Then test sudo -v and run finalize-debian.sh from that SSH session."
