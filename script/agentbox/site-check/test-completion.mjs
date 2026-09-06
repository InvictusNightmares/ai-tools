import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detectorResult } from './completion.mjs';

test('an initial zero score and saved page are not a completed scan', () => {
  const state = { byId: { 'score-value': '0', 'risk-badge': 'Ready to scan', 'result-title': '' }, retestDisabled: false };
  assert.equal(detectorResult('fuck-claude', state, false).completed, false);
  assert.equal(detectorResult('fuck-claude', state, true).completed, false);
});
test('a zero-risk finished scan is valid, while a disabled scanner is unfinished', () => {
  const state = { byId: { 'score-value': '0', 'risk-badge': 'Low risk', 'result-title': 'Scan result' }, retestDisabled: false };
  assert.equal(detectorResult('fuck-claude', state, true).completed, true);
  assert.equal(detectorResult('fuck-claude', { ...state, retestDisabled: true }, true).completed, false);
});
test('Net.Coffee must finish every panel; a DNS warning is a completed finding', () => {
  const byId = { gaugeScore: '75 良好', ipAddrClaude: '192.0.2.10', propsContent: '机房IP', securityContent: '未检测到',
    claudeAvailContent: '正常', dnsLeakContent: '可能泄露', udpLeakContent: '检测中', deviceContent: 'en-US' };
  assert.equal(detectorResult('net-coffee-claude', { byId }).completed, false);
  byId.udpLeakContent = 'WebRTC 已禁用或无泄露';
  assert.equal(detectorResult('net-coffee-claude', { byId }).completed, true);
  byId.gaugeScore = '--';
  assert.equal(detectorResult('net-coffee-claude', { byId }).completed, false);
});
