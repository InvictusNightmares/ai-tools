#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yaml'

# Offline source model, NOT a call to 3x-ui's Go implementation or Mihomo.
# 3x-ui v3.7.0: remote groups replace equal names; unmatched base groups remain.
# https://github.com/MHSanaei/3x-ui/blob/v3.7.0/internal/sub/clash_service.go#L827-L850
# https://github.com/MHSanaei/3x-ui/blob/v3.7.0/internal/sub/clash_service.go#L1021-L1079
# The simple filters below also model Mihomo v1.19.29's sorted include-all-proxies.
# https://github.com/MetaCubeX/mihomo/blob/v1.19.29/adapter/outboundgroup/parser.go#L95-L114

def check(condition, message)
  raise message unless condition
end

def merge_remote(overlay, nodes)
  base = {
    'proxies' => nodes.map { |name| { 'name' => name } },
    'proxy-groups' => [{ 'name' => 'PROXY', 'type' => 'select', 'proxies' => nodes + ['DIRECT'] }],
    'rules' => ['MATCH,PROXY']
  }
  overlay.each do |key, value|
    case key
    when 'proxy-groups'
      names = value.map { |group| group.fetch('name').strip }
      # Remote order wins; the case-sensitive name is the complete replacement key.
      base[key] = value + base[key].reject { |group| names.include?(group.fetch('name').strip) }
    when 'rule-providers'
      base[key] = value
    when 'rules'
      next if value.empty?

      has_match = value.any? { |rule| rule.split(',', 2).first.strip.casecmp('MATCH').zero? }
      base[key] = has_match ? value : value + base[key]
    end
  end
  base
end

def check_references(config, scenario)
  groups = config.fetch('proxy-groups')
  known = %w[DIRECT REJECT REJECT-DROP REJECT-TINYGIF PASS GLOBAL]
  known += config.fetch('proxies').map { |proxy| proxy.fetch('name') }
  known += groups.map { |group| group.fetch('name').strip }
  groups.each do |group|
    refs = group.fetch('proxies', [])
    check(refs.is_a?(Array), "#{scenario}: #{group['name']} proxies must be a list")
    refs.each do |ref|
      check(ref.is_a?(String) && known.include?(ref.strip), "#{scenario}: #{group['name']} references unknown proxy #{ref.inspect}")
    end
    check(group.fetch('use', []).is_a?(Array) && group.fetch('use', []).empty?, "#{scenario}: remote groups cannot use proxy-providers")
  end
  providers = config.fetch('rule-providers', {})
  check(providers.is_a?(Hash), "#{scenario}: rule-providers must be a map")
  providers.each do |name, provider|
    check(name.is_a?(String) && !name.strip.empty? && provider.is_a?(Hash), "#{scenario}: invalid rule-provider")
    via = provider['proxy']
    check(via.nil? || (via.is_a?(String) && known.include?(via.strip)), "#{scenario}: provider #{name} references unknown proxy #{via.inspect}")
  end
  config.fetch('rules').each do |rule|
    parts = rule.split(',').map(&:strip)
    check(parts.length >= 2, "#{scenario}: invalid rule #{rule.inspect}")
    if parts.first.casecmp('RULE-SET').zero?
      check(parts.length >= 3 && providers.key?(parts[1]), "#{scenario}: unknown rule-provider in #{rule.inspect}")
    end
    parts.pop while parts.length > 1 && %w[no-resolve src].include?(parts.last.downcase)
    check(known.include?(parts.last), "#{scenario}: unknown rule target in #{rule.inspect}")
  end
end

def candidates(group, nodes)
  result = group.fetch('proxies', []).dup
  if group['include-all-proxies']
    filters = group.fetch('filter').split('`').map { |pattern| Regexp.new(pattern) }
    nodes.sort.each do |node|
      filters.each { |filter| result << node if filter.match?(node) }
    end
  end
  result.empty? ? [group.fetch('empty-fallback', 'COMPATIBLE')] : result
end

def resolved_auto_chain(groups, nodes)
  by_name = groups.each_with_object({}) { |group, map| map[group.fetch('name')] = group }
  auto = by_name.fetch('Auto')
  candidates(auto, nodes).flat_map do |member|
    by_name.key?(member) ? candidates(by_name[member], nodes) : [member]
  end
end

begin
  check(ARGV.length <= 1, "Usage: ruby #{$PROGRAM_NAME} [FILE|-]")
  input = ARGV.first || File.expand_path('../../config/clash/dmit-rules.yaml', __dir__)
  overlay = YAML.safe_load(input == '-' ? $stdin.read : File.read(input), aliases: false)
  check(overlay.is_a?(Hash), 'routing overlay must be a YAML map')
  rules = overlay['rules']
  check(rules.is_a?(Array) && !rules.empty?, 'rules must be a non-empty list')
  check(rules.all? { |rule| rule.is_a?(String) && !rule.strip.empty? }, 'rules must contain only non-empty scalar strings')
  check(rules.uniq.length == rules.length, 'rules contain duplicate scalar strings')
  groups = overlay['proxy-groups']
  check(groups.is_a?(Array), 'proxy-groups must be a list')
  check(groups.all? { |group| group.is_a?(Hash) && group['name'].is_a?(String) && !group['name'].strip.empty? && group['type'].is_a?(String) && !group['type'].strip.empty? }, 'proxy-groups must contain named maps with a type')
  names = groups.map { |group| group.fetch('name').strip }
  check(names.uniq.length == names.length, 'duplicate remote proxy-group names')

  # Performance and DNS-avoidance rule invariants
  providers = overlay.fetch('rule-providers', {})
  ad_domain = providers['johnshall-shadowrocket-ad-domain']
  ad_ip = providers['johnshall-shadowrocket-ad-ip']
  check(ad_domain.is_a?(Hash) && ad_domain['behavior'] == 'domain' && ad_domain['format'] == 'text', 'johnshall-shadowrocket-ad-domain must be a text domain provider')
  check(ad_ip.is_a?(Hash) && ad_ip['behavior'] == 'ipcidr' && ad_ip['format'] == 'text', 'johnshall-shadowrocket-ad-ip must be a text ipcidr provider')
  check(rules.include?('GEOIP,private,DIRECT,no-resolve'), 'GEOIP,private,DIRECT must carry no-resolve')
  check(!rules.include?('GEOIP,private,DIRECT'), 'GEOIP,private,DIRECT without no-resolve must not appear')
  check(rules.include?('RULE-SET,johnshall-shadowrocket-ad-domain,REJECT'), 'ad domain provider rule must exist')
  check(rules.include?('RULE-SET,johnshall-shadowrocket-ad-ip,REJECT,no-resolve'), 'ad ipcidr provider rule must carry no-resolve')
  cn_idx = rules.index('GEOSITE,CN,DIRECT')
  non_cn_idx = rules.index('GEOSITE,geolocation-!cn,PROXY')
  geoip_cn_idx = rules.index('GEOIP,CN,DIRECT')
  check(cn_idx && non_cn_idx && geoip_cn_idx && cn_idx < non_cn_idx && non_cn_idx < geoip_cn_idx, 'GEOSITE,geolocation-!cn,PROXY must appear after GEOSITE,CN,DIRECT and before GEOIP,CN,DIRECT')

  scenarios = {
    'legacy nodes' => [%w[Vless Hysteria2 unrelated-node Hysteria2-copy Vless-copy], %w[Vless Hysteria2], %w[Auto Hysteria2 Vless]],
    'legacy Vless only' => [%w[Vless], %w[Vless REJECT], %w[Auto Vless]],
    'legacy Hysteria2 only' => [%w[Hysteria2], %w[REJECT Hysteria2], %w[Auto Hysteria2]],
    'US and SG nodes' => [%w[US-Vless US-Hysteria2 SG-Vless SG-Hysteria2 US-Vless-copy SG-Hysteria2-copy unrelated-node], %w[US-Vless US-Hysteria2], %w[Auto SG-Hysteria2 SG-Vless US-Hysteria2 US-Vless]],
    'main subscription with one server relay' => [
      %w[US-Hysteria2 US-Vless SG-Vless US-Vless-SG-Hysteria2 US-Vless-iOS],
      %w[US-Vless US-Hysteria2],
      %w[Auto SG-Vless US-Hysteria2 US-Vless US-Vless-SG-Hysteria2]
    ],
    'seven direct and relay nodes' => [
      %w[US-Hysteria2 US-Vless SG-Vless US-Hysteria2-SG-Hysteria2 US-Vless-SG-Hysteria2 US-Hysteria2-SG-Vless US-Vless-SG-Vless SG-Hysteria2 US-Vless-SG-Vless-copy unrelated-node],
      %w[US-Vless US-Hysteria2],
      %w[Auto SG-Hysteria2 SG-Vless US-Hysteria2 US-Hysteria2-SG-Hysteria2 US-Hysteria2-SG-Vless US-Vless US-Vless-SG-Hysteria2 US-Vless-SG-Vless]
    ],
    'relay nodes without US direct' => [%w[US-Hysteria2-SG-Hysteria2 US-Vless-SG-Vless], %w[REJECT REJECT], %w[Auto US-Hysteria2-SG-Hysteria2 US-Vless-SG-Vless]],
    'US nodes only' => [%w[US-Vless US-Hysteria2], %w[US-Vless US-Hysteria2], %w[Auto US-Hysteria2 US-Vless]],
    'SG nodes only' => [%w[SG-Vless SG-Hysteria2], %w[REJECT REJECT], %w[Auto SG-Hysteria2 SG-Vless]],
    'partial US rename' => [%w[US-Vless Hysteria2 SG-Vless SG-Hysteria2], %w[US-Vless Hysteria2], %w[Auto Hysteria2 SG-Hysteria2 SG-Vless US-Vless]],
    '3x-ui validation-node' => [%w[validation-node], %w[REJECT REJECT], %w[Auto]]
  }
  scenarios.each do |scenario, (nodes, expected_auto_chain, expected_proxy)|
    config = merge_remote(overlay, nodes)
    merged_groups = config.fetch('proxy-groups')
    merged_names = merged_groups.map { |group| group.fetch('name') }
    check(merged_names.sort == %w[Auto Auto-Hysteria2 Auto-Vless PROXY], "#{scenario}: expected Auto helpers, Auto, and PROXY after remote merge; got #{merged_names.join(', ')}")
    check_references(config, scenario)
    auto_vless = merged_groups.find { |group| group['name'] == 'Auto-Vless' }
    auto_hy2 = merged_groups.find { |group| group['name'] == 'Auto-Hysteria2' }
    auto = merged_groups.find { |group| group['name'] == 'Auto' }
    proxy = merged_groups.find { |group| group['name'] == 'PROXY' }
    check(auto_vless['hidden'] == true && auto_hy2['hidden'] == true && auto['hidden'] == true && proxy['hidden'] != true, "#{scenario}: only PROXY must be visible")
    check(auto_vless['type'] == 'select' && auto_vless['include-all-proxies'] == true && auto_vless['empty-fallback'] == 'REJECT', "#{scenario}: Auto-Vless must dynamically filter VLESS with REJECT empty-fallback")
    check(auto_hy2['type'] == 'select' && auto_hy2['include-all-proxies'] == true && auto_hy2['empty-fallback'] == 'REJECT', "#{scenario}: Auto-Hysteria2 must dynamically filter Hysteria2 with REJECT empty-fallback")
    check(auto['type'] == 'fallback' && auto['proxies'] == %w[Auto-Vless Auto-Hysteria2] && auto['empty-fallback'] == 'REJECT', "#{scenario}: Auto must use fallback prioritizing Auto-Vless over Auto-Hysteria2")
    check(resolved_auto_chain(merged_groups, nodes) == expected_auto_chain, "#{scenario}: Auto failover chain must prioritize VLESS then Hysteria2, falling back to REJECT when missing")
    check(proxy['type'] == 'select' && proxy.fetch('proxies', []).include?('Auto'), "#{scenario}: PROXY must offer Auto")
    check(proxy['default-selected'] == 'Auto', "#{scenario}: PROXY must default to Auto")
    check(candidates(proxy, nodes) == expected_proxy, "#{scenario}: PROXY must offer only Auto and matching nodes, never the default DIRECT candidate")
    check(config.fetch('rules').last == 'MATCH,PROXY', "#{scenario}: final rule must be MATCH,PROXY")
    puts "PASS: #{scenario}"
  end
  puts "PASS: #{rules.length} unique scalar rules; one visible PROXY group (offline source model)"
rescue Psych::Exception, Errno::ENOENT, ArgumentError, RuntimeError => e
  warn "FAIL: #{e.message}"
  exit 1
end
