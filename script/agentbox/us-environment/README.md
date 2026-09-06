# Agentbox US environment

This opt-in profile is for the finalized Agentbox cloud computer. It keeps the
DMIT **online subscription and its existing 720-minute refresh interval**, then
applies a local policy after the imported Clash Verge enhancement chain.

- `AGENTBOX-US` uses VLESS/Hysteria2 nodes from the configured DMIT IP only. If a
  refresh contains no eligible node, compilation fails and keeps the current
  working configuration. There is no DIRECT fallback for public destinations.
- Public DNS uses Cloudflare (`https://1.1.1.1/dns-query`), Google
  (`https://8.8.8.8/dns-query`), and Quad9 (`tls://9.9.9.9`), all through that
  proxy group with normal certificate verification. Quad9 DoT is used because
  its HTTPS endpoints timed out from the DMIT exit during live validation.
- The host uses local DNS, and Docker uses the host's bridge address. Only the
  local machine and Agentbox egress bridge can reach the DNS listener; UFW
  retains its default deny inbound policy. Tailnet names use Tailscale MagicDNS.
- The production TUN handles applications that do not honor HTTP proxy variables.
  Tailscale, local networks, and the DMIT transport remain outside the TUN.
  A separate nftables OUTPUT/FORWARD gate prevents normal public traffic and
  plaintext DNS from falling back to the physical `ens3` interface.
- The rescue proxy on 7897 has its own encrypted DNS and remains independent of
  the production proxy on 7898. SSH remains key-only, with root SSH disabled.
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

Validate actual UDP/TCP DNS, a fresh key SSH connection, public egress with proxy
variables disabled, container egress, and `sudo site-check`. Test the stopped
production case before removing the installation backup. Remove task upload
archives, intermediate reports, and Docker build cache after final acceptance;
retain the current image, configuration, dependency files, and final reports.

`fuck-claude` is a third-party heuristic, not an Anthropic acceptance test. Its
Emoji item assigns Linux a small nonzero score solely from `navigator.platform`
and the user agent. That score is not evidence of Chinese DNS, fonts, or locale.
The physical cloud region and the DMIT datacenter IP classification are unchanged.
