# Agentbox US environment

This opt-in profile is for the finalized Agentbox cloud computer. It keeps the
DMIT **online subscription and its existing 720-minute refresh interval**.
The downloaded rules, rule providers and routing groups remain unchanged;
desktop merge/scripts are skipped for this cloud profile. Local settings only
adapt DNS, TUN and headless runtime ports.

- `AGENTBOX-US` is an added DNS-only group using VLESS/Hysteria2 nodes from the configured DMIT IP. If a
  refresh contains no eligible node, compilation fails and keeps the current
  working configuration. DNS has no DIRECT fallback. Ordinary traffic follows
  the subscription's original DIRECT/REJECT/PROXY rules and their original order.
- Public DNS uses Cloudflare (`https://1.1.1.1/dns-query`), Google
  (`https://8.8.8.8/dns-query`), and Quad9 (`tls://9.9.9.9`), all through that
  proxy group with normal certificate verification. Quad9 DoT is used because
  its HTTPS endpoints timed out from the DMIT exit during live validation.
- The host uses local DNS, and Docker uses the host's bridge address. Only the
  local machine and Agentbox egress bridge can reach the DNS listener; UFW
  retains its default deny inbound policy. Tailnet names use Tailscale MagicDNS.
- The production TUN handles applications that do not honor HTTP proxy variables.
  Tailscale, local networks, and the DMIT transport remain outside the TUN.
  A separate nftables OUTPUT/FORWARD gate keeps ordinary processes behind the
  TUN and blocks external port 53/853 DNS bypasses. The `mihomo` service UID may
  reach public destinations directly when the subscription says DIRECT.
- Chrome uses the managed `WebRtcIPHandling=disable_non_proxied_udp` policy,
  so WebRTC does not independently expose an IP through non-proxied UDP.
- Both 7897 and 7898 use the same downloaded subscription rules, providers and
  groups. Tailscale, Docker downloads and subscription downloads use 7897;
  ordinary shell/container traffic uses 7898. Only 7898 enables the TUN.
  Each process keeps its own configuration, data cache and encrypted DNS:
  7897 listens on loopback port 1054, 7898 on port 53, and update candidates on
  loopback port 1053. DNS policy remains identical across all three.
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
matches, UDP/TCP DNS, a fresh key SSH connection, container egress, and `site-check`.
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
The physical cloud region and the DMIT datacenter IP classification are unchanged.
