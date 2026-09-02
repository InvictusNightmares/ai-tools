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

  scenarios = {
    'both nodes' => [%w[Vless Hysteria2 unrelated-node Hysteria2-copy Vless-copy], %w[Hysteria2 Vless]],
    'Vless only' => [%w[Vless], %w[Vless]],
    'Hysteria2 only' => [%w[Hysteria2], %w[Hysteria2]],
    '3x-ui validation-node' => [%w[validation-node], %w[REJECT]]
  }
  scenarios.each do |scenario, (nodes, expected_auto)|
    config = merge_remote(overlay, nodes)
    merged_groups = config.fetch('proxy-groups')
    merged_names = merged_groups.map { |group| group.fetch('name') }
    check(merged_names.sort == %w[Auto PROXY], "#{scenario}: expected only Auto and PROXY after remote merge; got #{merged_names.join(', ')}")
    check_references(config, scenario)
    auto = merged_groups.find { |group| group['name'] == 'Auto' }
    proxy = merged_groups.find { |group| group['name'] == 'PROXY' }
    check(auto['hidden'] == true && proxy['hidden'] != true, "#{scenario}: only Auto must be hidden")
    check(auto['type'] == 'fallback' && auto['include-all-proxies'] == true && auto.fetch('proxies', []).empty?, "#{scenario}: Auto must dynamically include nodes, not hard-code them")
    check(auto['empty-fallback'] == 'REJECT', "#{scenario}: an empty Auto must REJECT, never go DIRECT")
    check(candidates(auto, nodes) == expected_auto, "#{scenario}: Auto must prefer Hysteria2, then Vless, or REJECT when empty")
    check(proxy['type'] == 'select' && proxy.fetch('proxies', []).include?('Auto'), "#{scenario}: PROXY must offer Auto")
    check(proxy['default-selected'] == 'Auto', "#{scenario}: PROXY must default to Auto")
    expected_proxy = ['Auto'] + (expected_auto == ['REJECT'] ? [] : expected_auto)
    check(candidates(proxy, nodes) == expected_proxy, "#{scenario}: PROXY must offer only Auto and matching nodes, never the default DIRECT candidate")
    check(config.fetch('rules').last == 'MATCH,PROXY', "#{scenario}: final rule must be MATCH,PROXY")
    puts "PASS: #{scenario}"
  end
  puts "PASS: #{rules.length} unique scalar rules; one visible PROXY group (offline source model)"
rescue Psych::Exception, Errno::ENOENT, ArgumentError, RuntimeError => e
  warn "FAIL: #{e.message}"
  exit 1
end
