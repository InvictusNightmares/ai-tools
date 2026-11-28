# Agentbox US environment

This opt-in profile is for the finalized Agentbox cloud computer. It keeps the
configured **online subscription and its existing 720-minute refresh interval**.
The downloaded rules, rule providers and routing groups remain unchanged;
desktop merge/scripts are skipped for this cloud profile. Local settings only
adapt DNS, TUN and headless runtime ports.

- `AGENTBOX-US` is an added DNS-only fallback group using direct primary VLESS/Hysteria2 nodes from the privately configured primary proxy address (excluding cross-region relay nodes). On port `7897` (`mihomo-bootstrap`), `AGENTBOX-BOOTSTRAP` extends the fallback chain with any privately configured `fallback-servers` (e.g. primary VLESS -> primary Hysteria2 -> secondary VLESS -> secondary Hysteria2) and routes bootstrap's `PROXY` group and overseas DNS through it so Tailscale and subscription updates survive primary outages or SNI rotations. If a refresh contains no eligible primary node, compilation fails closed and keeps the current working configuration.
- Split zero-leak encrypted DNS: domestic/private domains (`geosite:cn,private`, NTP, and standard connectivity probes; no STUN wildcards) resolve via literal-IP domestic DoH (`https://223.5.5.5/dns-query#DIRECT`, `https://1.12.12.12/dns-query#DIRECT`) with zero plaintext port-53 bootstrap lookups; Tailnet names use Tailscale MagicDNS (`100.100.100.100#tailscale0`); all other overseas domains resolve 100% through `https://1.1.1.1/dns-query` and `https://8.8.8.8/dns-query` over `AGENTBOX-US` (or `AGENTBOX-BOOTSTRAP` on `7897`).
- Runtime tuning aligns with the client baseline: `ipv6: false`, `log-level: warning`, `tcp-concurrent: true`, `keep-alive-idle: 15`, `keep-alive-interval: 15`, `geo-auto-update: true`, `profile.store-selected: false`, overseas UDP/443 QUIC rejection from the online ruleset, and `backlog=128` on `agentbox-container-proxy`.
- The host uses local DNS (`/etc/resolv.conf` pinned to `127.0.0.1` and protected against `dhcpcd` overwrites), and Docker uses the host's bridge address (`172.18.0.1`). Only the local machine and Agentbox egress bridge can reach the DNS listener; UFW retains its default deny inbound policy.
- The production TUN handles applications that do not honor HTTP proxy variables. Tailscale, local networks, and all configured primary/fallback proxy transport IPs remain outside the TUN. A separate nftables OUTPUT/FORWARD gate keeps ordinary processes behind the TUN and blocks external port 53/853 DNS bypasses before the `mihomo` service UID exception, while still letting `mihomo` honor domestic `DIRECT` rules and `fwmark 0x80000` Tailscale traffic.
- Chrome uses the managed `WebRtcIPHandling=disable_non_proxied_udp` policy, so WebRTC does not independently expose an IP through non-proxied UDP.
- Tailscale and subscription downloads use `7897` (`mihomo-bootstrap`); Docker image pulls and ordinary shell/container traffic use `7898` (`mihomo`). Only `7898` enables the TUN. Each process keeps its own configuration, data cache and encrypted DNS: `7897` listens on loopback port `1054`, `7898` on port `53`, and update candidates on loopback port `1053`. See [refactor-2026-11.md](../../../doc/agentbox/refactor-2026-11.md) for the full 2026-11 refactor details.
- Each refresh downloads once and validates before activating either instance.
  Unchanged configurations are not restarted. Any activation/health-check error
  restores both previous configurations; successful updates remove transaction
  backups. Download or validation failure leaves the running copies untouched.
  The processes are independent, but now share subscription routing changes;
  validation cannot guarantee every destination in a future subscription works.
  SSH remains key-only for the sole root administrator; password and
  keyboard-interactive authentication stay disabled.
- The derived, pinned Chrome image removes the actual `fonts-noto-cjk` and
  `fonts-wqy-zenhei` packages and keeps English/Unicode fallback fonts. There are
  no JavaScript overrides of fonts, timezone, user agent, or platform.

Run as root, from a reviewed repository copy on the existing cloud computer:

```sh
bash script/agentbox/us-environment/install.sh
```

The installer waits for an existing subscription update and pauses its timer
while changing settings. It records exact private rollback inputs under
`/root/agentbox-us-backup`, restores the timer even on early failure, and rolls
back installation errors. This is a first-install operation; subsequent online
refreshes use `update-agentbox-proxy --force`. Do not run a second installer over
an existing US egress service.

Validate exact equality with downloaded rules, actual DIRECT and PROXY log
matches, UDP/TCP DNS, a fresh key SSH connection, and container egress.
Run `node --test script/agentbox/test-profile-rules.mjs script/agentbox/test-proxy-transaction.mjs` and
`node script/agentbox/agentbox-profile-compiler.js --self-test` before deployment.
Existing installations must also add the Mihomo UID exception to the managed
nftables output chain, after its DNS-port rejection; changing YAML alone leaves
DIRECT connections blocked by the previous firewall policy. Install the updated
`systemd/agentbox-proxy-update.service` and run `systemctl daemon-reload` as well:
its filesystem allowlist must include both configuration and data directories.
When switching 7897 over a Tailscale SSH session, run the update under systemd
so transport reconnection cannot terminate it. Test the stopped
production case before removing the installation backup. Remove task upload
archives, intermediate reports, and Docker build cache after final acceptance;
retain the current image, configuration, dependency files, and final reports.

`fuck-claude` is a third-party heuristic, not an Anthropic acceptance test. Its
Emoji item assigns Linux a small nonzero score solely from `navigator.platform`
and the user agent. That score is not evidence of Chinese DNS, fonts, or locale.
The physical cloud region and the proxy endpoint classification are unchanged.
