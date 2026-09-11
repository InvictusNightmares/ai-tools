#!/usr/bin/env node

/**
 * Local-only experiment for the auto gateway route state machine.
 * It does not call a provider or read credentials.
 *
 * The numbers are normalized units, not provider prices:
 * - stable prefix: 4,000 tokens
 * - dynamic input: 500 tokens
 * - output: 300 tokens
 * - cache hit input costs 0.1 unit/token; miss costs 1 unit/token
 * - provider cache expires after 4 turns without using that model
 */

const MODELS = [
  { name: "deepseek-flash", tier: 0 },
  { name: "gpt-5.6-luna", tier: 1 },
  { name: "gpt-5.6-terra", tier: 2 },
  { name: "gpt-5.6-sol", tier: 3 },
  { name: "gpt-6-astra", tier: 4 },
];

const THRESHOLDS = [0, 21, 36, 56, 76];
const STABLE_PREFIX_TOKENS = 4_000;
const DYNAMIC_INPUT_TOKENS = 500;
const OUTPUT_TOKENS = 300;
const CACHE_HIT_PRICE = 0.1;
const CACHE_MISS_PRICE = 1;
const CACHE_TTL_TURNS = 4;
const UPGRADE_COOLDOWN_TURNS = 3;

// The first route epoch progressively becomes harder. The final two turns
// start a new topic and demonstrate that routing may reset to Flash.
const TASKS = [
  { label: "simple-qa-1", difficulty: 10 },
  { label: "simple-qa-2", difficulty: 10 },
  { label: "simple-qa-3", difficulty: 10 },
  { label: "small-code-fix-1", difficulty: 35 },
  { label: "small-code-fix-2", difficulty: 35 },
  { label: "small-code-fix-3", difficulty: 35 },
  { label: "multi-file-debug-1", difficulty: 60 },
  { label: "multi-file-debug-2", difficulty: 60 },
  { label: "multi-file-debug-3", difficulty: 60 },
  { label: "architecture-1", difficulty: 80 },
  { label: "architecture-2", difficulty: 80 },
  { label: "agent-workflow-1", difficulty: 95 },
  { label: "agent-workflow-2", difficulty: 95 },
  { label: "agent-quick-check-1", difficulty: 10 },
  { label: "agent-quick-check-2", difficulty: 10 },
  { label: "agent-quick-check-3", difficulty: 10 },
  { label: "agent-quick-check-4", difficulty: 10 },
  { label: "agent-quick-check-5", difficulty: 10 },
  { label: "agent-workflow-3", difficulty: 95 },
  { label: "new-topic-qa", difficulty: 10, newEpoch: true },
  { label: "new-topic-followup", difficulty: 10 },
  { label: "new-topic-complex", difficulty: 85 },
];

function targetTier(difficulty) {
  let tier = 0;
  for (let i = 0; i < THRESHOLDS.length; i += 1) {
    if (difficulty >= THRESHOLDS[i]) tier = i;
  }
  return tier;
}

function cacheCost(cacheHitTokens, cacheMissTokens) {
  return (
    cacheHitTokens * CACHE_HIT_PRICE +
    cacheMissTokens * CACHE_MISS_PRICE +
    OUTPUT_TOKENS
  );
}

function run(policy) {
  const state = {
    currentTier: 0,
    routeEpoch: 0,
    lastSwitchTurn: -Infinity,
    switches: 0,
    switchesInEpoch: 0,
    cache: new Map(),
  };
  const rows = [];

  for (let index = 0; index < TASKS.length; index += 1) {
    const turn = index + 1;
    const task = TASKS[index];
    if (task.newEpoch) {
      state.routeEpoch += 1;
      state.currentTier = 0;
      state.lastSwitchTurn = -Infinity;
      state.switchesInEpoch = 0;
    }

    const desiredTier = targetTier(task.difficulty);
    let nextTier = state.currentTier;
    if (policy === "per-turn") {
      nextTier = desiredTier;
    } else if (policy === "one-upgrade") {
      if (desiredTier > state.currentTier && state.switchesInEpoch === 0) {
        nextTier = desiredTier;
      }
    } else if (policy === "multi-upgrade") {
      const cooldownElapsed = turn - state.lastSwitchTurn >= UPGRADE_COOLDOWN_TURNS;
      if (desiredTier > state.currentTier && cooldownElapsed) {
        nextTier = desiredTier;
      }
    }

    const switched = nextTier !== state.currentTier;
    if (switched) {
      state.currentTier = nextTier;
      state.lastSwitchTurn = turn;
      state.switches += 1;
      state.switchesInEpoch += 1;
    }

    const model = MODELS[state.currentTier];
    const lastUsedTurn = state.cache.get(model.name);
    const cacheHit = lastUsedTurn !== undefined && turn - lastUsedTurn <= CACHE_TTL_TURNS;
    const cacheHitTokens = cacheHit ? STABLE_PREFIX_TOKENS : 0;
    const cacheMissTokens = cacheHit ? DYNAMIC_INPUT_TOKENS : STABLE_PREFIX_TOKENS + DYNAMIC_INPUT_TOKENS;
    state.cache.set(model.name, turn);

    const qualityRatio = Math.min(1, (state.currentTier + 1) / (desiredTier + 1));
    rows.push({
      turn,
      epoch: state.routeEpoch,
      task: task.label,
      desired: MODELS[desiredTier].name,
      selected: model.name,
      switched,
      cache: cacheHit ? "hit" : "miss",
      cacheHitTokens,
      cacheMissTokens,
      cost: cacheCost(cacheHitTokens, cacheMissTokens),
      qualityRatio,
    });
  }

  const totals = rows.reduce(
    (acc, row) => {
      acc.cost += row.cost;
      acc.cacheMissTokens += row.cacheMissTokens;
      acc.cacheHitTokens += row.cacheHitTokens;
      acc.quality += row.qualityRatio;
      if (row.cache === "hit") acc.cacheHits += 1;
      if (MODELS.find((model) => model.name === row.selected).tier < MODELS.find((model) => model.name === row.desired).tier) {
        acc.underTierTurns += 1;
      }
      return acc;
    },
    { cost: 0, cacheMissTokens: 0, cacheHitTokens: 0, cacheHits: 0, quality: 0, underTierTurns: 0 },
  );

  return {
    policy,
    rows,
    switches: state.switches,
    cacheHitRate: totals.cacheHits / rows.length,
    cacheMissTokens: totals.cacheMissTokens,
    cost: totals.cost,
    averageQuality: totals.quality / rows.length,
    underTierTurns: totals.underTierTurns,
  };
}

function printResult(result) {
  console.log(`\n=== ${result.policy} ===`);
  console.log(
    `switches=${result.switches}  cache_hit_rate=${(result.cacheHitRate * 100).toFixed(1)}%  ` +
      `cache_miss_tokens=${result.cacheMissTokens}  normalized_cost=${result.cost.toFixed(0)}  ` +
      `avg_quality=${(result.averageQuality * 100).toFixed(1)}%  under_tier_turns=${result.underTierTurns}`,
  );
  console.table(
    result.rows.map((row) => ({
      turn: row.turn,
      epoch: row.epoch,
      task: row.task,
      selected: row.selected,
      desired: row.desired,
      cache: row.cache,
      miss_tokens: row.cacheMissTokens,
      quality: `${(row.qualityRatio * 100).toFixed(0)}%`,
    })),
  );
}

for (const policy of ["per-turn", "one-upgrade", "multi-upgrade"]) {
  printResult(run(policy));
}
