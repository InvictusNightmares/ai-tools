#!/bin/sh
set -eu

bundle_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target=${1:-/target}

if [ "$target" != /target ] || [ ! -d "$target/etc" ] || [ ! -x "$target/bin/sh" ]; then
    echo 'Refusing to install the private proxy bundle outside the Debian installer target.' >&2
    exit 1
fi

for file in \
    mihomo config.yaml production.yaml \
    mihomo-bootstrap.service mihomo.service \
    agentbox-proxy-update.service agentbox-proxy-update.timer \
    agentbox-profile-compiler.js update-agentbox-proxy.sh; do
    [ -f "$bundle_dir/$file" ] || {
        echo "Private proxy bundle is incomplete: $file" >&2
        exit 1
    }
done
for directory in app-profile vendor; do
    [ -d "$bundle_dir/$directory" ] || {
        echo "Private proxy bundle is incomplete: $directory" >&2
        exit 1
    }
done

if ! chroot "$target" getent group mihomo >/dev/null 2>&1; then
    chroot "$target" groupadd --system mihomo
fi
if ! chroot "$target" getent passwd mihomo >/dev/null 2>&1; then
    chroot "$target" useradd --system --gid mihomo --home-dir /nonexistent --shell /usr/sbin/nologin mihomo
fi

mkdir -p \
    "$target/usr/local/bin" \
    "$target/usr/local/libexec/vendor" \
    "$target/usr/local/sbin" \
    "$target/etc/mihomo-bootstrap" \
    "$target/etc/mihomo" \
    "$target/etc/agentbox-profile" \
    "$target/etc/systemd/system" \
    "$target/etc/systemd/system/tailscaled.service.d" \
    "$target/etc/apt/apt.conf.d" \
    "$target/etc/profile.d" \
    "$target/var/lib/mihomo-bootstrap" \
    "$target/var/lib/mihomo" \
    "$target/var/lib/agentbox-profile"

cp "$bundle_dir/mihomo" "$target/usr/local/bin/mihomo"
cp "$bundle_dir/agentbox-profile-compiler.js" "$target/usr/local/libexec/agentbox-profile-compiler.js"
cp "$bundle_dir/vendor/js-yaml.cjs" "$target/usr/local/libexec/vendor/js-yaml.cjs"
cp "$bundle_dir/vendor/js-yaml.LICENSE" "$target/usr/local/libexec/vendor/js-yaml.LICENSE"
cp "$bundle_dir/update-agentbox-proxy.sh" "$target/usr/local/sbin/update-agentbox-proxy"
cp "$bundle_dir/config.yaml" "$target/etc/mihomo-bootstrap/config.yaml"
cp "$bundle_dir/production.yaml" "$target/etc/mihomo/config.yaml"
cp "$bundle_dir/production.yaml" "$target/etc/mihomo/config.yaml.previous"
cp -a "$bundle_dir/app-profile/." "$target/etc/agentbox-profile/"

for unit in mihomo-bootstrap.service mihomo.service agentbox-proxy-update.service agentbox-proxy-update.timer; do
    cp "$bundle_dir/$unit" "$target/etc/systemd/system/$unit"
done

for file in Country.mmdb geoip.dat geosite.dat cache.db; do
    if [ -f "$bundle_dir/$file" ]; then
        cp "$bundle_dir/$file" "$target/var/lib/mihomo-bootstrap/$file"
        cp "$bundle_dir/$file" "$target/var/lib/mihomo/$file"
    fi
done
if [ -d "$bundle_dir/ruleset" ]; then
    mkdir -p "$target/var/lib/mihomo/ruleset"
    cp -a "$bundle_dir/ruleset/." "$target/var/lib/mihomo/ruleset/"
fi

cat >"$target/etc/apt/apt.conf.d/80agentbox-proxy" <<'EOF'
Acquire::http::Proxy "http://127.0.0.1:7897/";
Acquire::https::Proxy "http://127.0.0.1:7897/";
EOF
cat >"$target/etc/profile.d/agentbox-proxy.sh" <<'EOF'
export http_proxy=http://127.0.0.1:7897
export https_proxy=http://127.0.0.1:7897
export HTTP_PROXY=http://127.0.0.1:7897
export HTTPS_PROXY=http://127.0.0.1:7897
EOF
cat >"$target/etc/systemd/system/tailscaled.service.d/proxy.conf" <<'EOF'
[Unit]
Wants=mihomo-bootstrap.service
After=mihomo-bootstrap.service

[Service]
Environment=HTTP_PROXY=http://127.0.0.1:7897
Environment=HTTPS_PROXY=http://127.0.0.1:7897
EOF

chmod 0755 \
    "$target/usr/local/bin/mihomo" \
    "$target/usr/local/libexec/agentbox-profile-compiler.js" \
    "$target/usr/local/sbin/update-agentbox-proxy"
chmod 0644 "$target/usr/local/libexec/vendor/js-yaml.cjs" "$target/usr/local/libexec/vendor/js-yaml.LICENSE"
chmod 0750 "$target/etc/mihomo-bootstrap" "$target/etc/mihomo"
chmod 0640 \
    "$target/etc/mihomo-bootstrap/config.yaml" \
    "$target/etc/mihomo/config.yaml" \
    "$target/etc/mihomo/config.yaml.previous"
chmod 0700 "$target/etc/agentbox-profile"
find "$target/etc/agentbox-profile" -type d -exec chmod 0700 {} \;
find "$target/etc/agentbox-profile" -type f -exec chmod 0600 {} \;
chmod 0750 "$target/var/lib/mihomo-bootstrap" "$target/var/lib/mihomo"
chmod 0700 "$target/var/lib/agentbox-profile"
chroot "$target" chown root:mihomo \
    /etc/mihomo-bootstrap/config.yaml \
    /etc/mihomo/config.yaml \
    /etc/mihomo/config.yaml.previous
chroot "$target" chown -R mihomo:mihomo /var/lib/mihomo-bootstrap /var/lib/mihomo
chroot "$target" chown -R root:root /etc/agentbox-profile /var/lib/agentbox-profile

chroot "$target" systemctl enable mihomo-bootstrap.service mihomo.service

echo 'Installed the private bootstrap and production proxy layers into the Debian target.'
