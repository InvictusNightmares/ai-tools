// These IDs and labels were inspected on the real detector pages from Agentbox.
export function detectorResult(name, state, scanTriggered = false) {
  const text = id => (state.byId[id] ?? '').trim();
  const number = value => /^\d{1,3}(?:\s|$)/.test(value) ? Number(value.match(/^\d+/)[0]) : NaN;
  const score = number(text(name === 'net-coffee-claude' ? 'gaugeScore' : 'score-value'));
  const scoreReady = Number.isFinite(score) && score >= 0 && score <= 100;
  if (name === 'net-coffee-claude') {
    const sections = ['propsContent', 'securityContent', 'claudeAvailContent', 'dnsLeakContent', 'udpLeakContent', 'deviceContent'];
    const completed = scoreReady && /^\d{1,3}(\.\d{1,3}){3}$/.test(text('ipAddrClaude')) &&
      sections.every(id => text(id) && !/检测中|加载中|查询中|Loading|Checking/i.test(text(id)));
    return { completed, score: scoreReady ? score : null, rating: text('gaugeScore'),
      claudeIp: text('ipAddrClaude'), cloudflareIp: text('ipAddr'), domesticIp: text('ipAddrCN'),
      location: text('ipGeoClaude'), properties: text('propsContent'), security: text('securityContent'),
      availability: text('claudeAvailContent'), dns: text('dnsLeakContent'), webrtc: text('udpLeakContent'), device: text('deviceContent') };
  }
  if (name === 'fuck-claude') {
    const badge = text('risk-badge');
    const completed = scanTriggered && scoreReady && /^(Low|Medium|High)\b|^(低|中|高)风险/i.test(badge) &&
      Boolean(text('result-title')) && state.retestDisabled === false;
    return { completed, score: scoreReady ? score : null, rating: badge,
      description: text('risk-desc'), title: text('result-title'), hits: text('result-hits'), details: text('result') };
  }
  throw new Error('Unknown detector');
}
