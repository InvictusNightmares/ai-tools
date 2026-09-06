#!/usr/bin/env bash
set -euo pipefail
# The base Docker guard permits traditional bridge names. Allow the named
# Agentbox bridge only towards the US TUN; physical fallback remains blocked.
if ! iptables -w -C AGENTBOX-DOCKER -i ab-egress0 -o ab-us -j ACCEPT >/dev/null 2>&1; then
  iptables -w -I AGENTBOX-DOCKER 2 -i ab-egress0 -o ab-us -j ACCEPT
fi
