import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const packageRoot = path.resolve(process.env.PACKAGE_ROOT || ".");
const outputDir = path.resolve(process.env.OUTPUT_DIR || path.join(packageRoot, "outputs"));
const methods = JSON.parse(await fs.readFile(path.join(packageRoot, "research", "methods.json"), "utf8"));
const sources = JSON.parse(await fs.readFile(path.join(packageRoot, "research", "sources.json"), "utf8"));
const weights = [0.20, 0.15, 0.10, 0.15, 0.15, 0.15, 0.10];
const weightNames = ["需求证据", "验证速度", "低成本", "复购性", "自动化杠杆", "获客可达", "风险可控"];
const topOrder = new Map([[20, 0], [1, 1], [22, 2]]);

const color = {
  navy: "#14213D",
  teal: "#0F766E",
  tealLight: "#CCFBF1",
  amber: "#F59E0B",
  amberLight: "#FEF3C7",
  blueLight: "#DBEAFE",
  gray: "#64748B",
  grayLight: "#F1F5F9",
  border: "#CBD5E1",
  white: "#FFFFFF",
  green: "#166534",
};

function numbers(text) {
  return [...text.matchAll(/\d[\d,]*/g)].map((m) => Number(m[0].replaceAll(",", "")));
}

function maxCost(text) {
  const found = numbers(text);
  return found.length ? Math.max(...found) : 0;
}

function validationDays(method) {
  const match = (method.time + " " + method.validation).match(/(\d+)[–-](\d+)\s*天/);
  if (match) return Number(match[2]);
  const single = method.time.match(/(\d+)\s*天/);
  return single ? Number(single[1]) : 30;
}

function difficulty(method) {
  const [_, speed, lowCost, __, ___, access] = method.score;
  return Math.max(1, Math.min(5, Math.round(((6 - speed) + (6 - lowCost) + (6 - access)) / 3)));
}

function totalScore(method) {
  const raw = method.score.reduce((sum, value, i) => sum + value * weights[i], 0);
  // Match build_package.py exactly: rank on the two-decimal published score,
  // then use method ID as the deterministic tie-breaker.
  return Math.round((raw + Number.EPSILON) * 100) / 100;
}

const orderedMethods = [...methods].sort((a, b) => {
  const aTop = topOrder.has(a.id);
  const bTop = topOrder.has(b.id);
  if (aTop && bTop) return topOrder.get(a.id) - topOrder.get(b.id);
  if (aTop) return -1;
  if (bTop) return 1;
  return totalScore(b) - totalScore(a) || a.id - b.id;
});

function styleTitle(sheet, range, value) {
  range.merge();
  range.values = [[value]];
  range.format = {
    fill: color.navy,
    font: { bold: true, color: color.white, size: 20 },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  range.format.rowHeight = 32;
}

function styleHeader(range) {
  range.format = {
    fill: color.teal,
    font: { bold: true, color: color.white },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: color.border },
  };
  range.format.rowHeight = 30;
}

const workbook = Workbook.create();
const overview = workbook.worksheets.add("优先级");
const comparison = workbook.worksheets.add("50项目对比");
const parameters = workbook.worksheets.add("评分参数");
const sourceSheet = workbook.worksheets.add("来源");

for (const sheet of [overview, comparison, parameters, sourceSheet]) {
  sheet.showGridLines = false;
}

// Rating parameters are the visible source of truth for overall score formulas.
styleTitle(parameters, parameters.getRange("A1:D2"), "评分参数｜可编辑；总权重应为 100%");
parameters.getRange("A3:D3").values = [["评分项", "权重", "5 分含义", "使用说明"]];
styleHeader(parameters.getRange("A3:D3"));
const descriptions = [
  "有当前一手需求、渠道或强痛点证据",
  "7 天左右可出样品，30 天可收费",
  "现金启动成本很低",
  "月费/复检/续订自然成立",
  "交付可复用、自动化或数字化",
  "可合法触达买方且付款路径可行",
  "许可、隐私、平台与责任边界清楚",
];
const parameterRows = weightNames.map((name, i) => [name, weights[i], descriptions[i], "编辑蓝色权重；综合分与 P 级自动重算"]);
parameters.getRange("A4:D10").values = parameterRows;
parameters.getRange("A11:D11").values = [["权重合计", null, "应等于 100%", "若不等于 100%，综合分仍会按实际权重计算"]];
parameters.getRange("B11").formulas = [["=SUM(B4:B10)"]];
parameters.getRange("B4:B11").format.numberFormat = "0%";
parameters.getRange("B4:B10").format = { fill: color.blueLight, font: { bold: true, color: color.navy } };
parameters.getRange("A4:D11").format = {
  verticalAlignment: "top",
  wrapText: true,
  borders: { preset: "inside", style: "thin", color: color.border },
};
parameters.getRange("A11:D11").format = { fill: color.amberLight, font: { bold: true }, borders: { preset: "outside", style: "thin", color: color.amber } };
parameters.getRange("A12:D14").merge();
parameters.getRange("A12:D14").values = [["编辑说明：蓝色权重变更后，综合分、P1/P2/P3 与动态排序键自动重算；前三项“首做”始终锁定 20→01→22。数据行不会自动移动，请在“50项目对比”表点击“动态排序键”筛选箭头 > 从小到大排序。收益列是测试情景，不是保证。"]];
parameters.getRange("A12:D14").format = { fill: color.grayLight, font: { color: color.gray, italic: true }, wrapText: true, verticalAlignment: "center" };
parameters.getRange("A:A").format.columnWidth = 16;
parameters.getRange("B:B").format.columnWidth = 10;
parameters.getRange("C:C").format.columnWidth = 34;
parameters.getRange("D:D").format.columnWidth = 36;
parameters.freezePanes.freezeRows(3);

// Main comparison table.
styleTitle(comparison, comparison.getRange("A1:X1"), "50 个当前可执行赚钱项目｜统一对比");
comparison.getRange("A2:X2").merge();
comparison.getRange("A2:X2").values = [["快照：2026-09-01｜前三行锁定人工首做顺序 20→01→22，其余为默认权重下的初始降序。改权重后点击“动态排序键”筛选箭头 > 从小到大排序：前三不动，其余按新综合分降序、ID 升序。收益不是保证。"]];
comparison.getRange("A2:X2").format = { fill: color.grayLight, font: { color: color.gray, italic: true }, wrapText: true, verticalAlignment: "center" };
comparison.getRange("A4:X4").values = [[
  "动态优先级", "ID", "方法", "类别", "启动成本上限", "难度", "验证天数", "保守月营收", "中性月营收", "乐观月营收",
  "需求", "速度", "低成本", "复购", "自动化", "获客", "风险可控", "综合分", "成本口径 / 参考测试报价", "最小付费验证", "主要风险", "首要来源URL", "方法文件", "动态排序键",
]];
styleHeader(comparison.getRange("A4:X4"));
const comparisonRows = orderedMethods.map((m) => [
  null, m.id, m.title, m.category, maxCost(m.cost), difficulty(m), validationDays(m), m.monthly[0], m.monthly[1], m.monthly[2],
  ...m.score, null, `启动成本：${m.cost}；报价：${m.price}`, m.validation, m.risks[0][0], sources[m.sources[0]].url, `methods/${String(m.id).padStart(2, "0")}-${m.slug}.md`, null,
]);
const comparisonRowById = new Map(orderedMethods.map((method, index) => [method.id, index + 5]));
comparison.getRange("A5:X54").values = comparisonRows;
comparison.getRange("R5").formulas = [["=ROUND(K5*'评分参数'!$B$4+L5*'评分参数'!$B$5+M5*'评分参数'!$B$6+N5*'评分参数'!$B$7+O5*'评分参数'!$B$8+P5*'评分参数'!$B$9+Q5*'评分参数'!$B$10,2)"]];
comparison.getRange("R5:R54").fillDown();
// Build P-level labels from a non-cell-like string plus a number. This avoids
// fillDown treating literals such as "P1" as relative A1 references.
comparison.getRange("A5").formulas = [["=IF(B5=20,\"首做\",IF(B5=1,\"首做\",IF(B5=22,\"首做\",IF(R5>=4.55,\"P\"&1,IF(R5>=4.10,\"P\"&2,\"P\"&3)))))"]];
comparison.getRange("A5:A54").fillDown();
comparison.getRange("X5").formulas = [["=IF(B5=20,1,IF(B5=1,2,IF(B5=22,3,1000-R5*100+B5/1000)))"]];
comparison.getRange("X5:X54").fillDown();

// Regression gate: editable weights must update the published score and P level.
// Row order is intentionally user-sorted via the table control documented above.
parameters.getRange("B4:B10").values = [[0], [0.35], [0.10], [0.15], [0.15], [0.15], [0.10]];
const scenarioExpectations = new Map([[2, [4.60, "P1"]], [3, [4.40, "P2"]]]);
for (const [id, [expectedScore, expectedPriority]] of scenarioExpectations) {
  const row = comparisonRowById.get(id);
  const values = comparison.getRange(`A${row}:R${row}`).values[0];
  if (values[0] !== expectedPriority || Math.abs(values[17] - expectedScore) > 1e-9) {
    throw new Error(`weight scenario regression for method ${id}: ${values[0]} / ${values[17]}`);
  }
}
for (const id of [20, 1, 22]) {
  const row = comparisonRowById.get(id);
  if (comparison.getRange(`A${row}`).values[0][0] !== "首做") {
    throw new Error(`manual top-three priority changed for method ${id}`);
  }
}
const scenarioOrder = orderedMethods
  .map((method) => {
    const row = comparisonRowById.get(method.id);
    return [method.id, comparison.getRange(`X${row}`).values[0][0]];
  })
  .sort((a, b) => a[1] - b[1])
  .map(([id]) => id);
if (scenarioOrder.slice(0, 3).join(",") !== "20,1,22" || scenarioOrder.indexOf(2) >= scenarioOrder.indexOf(3)) {
  throw new Error(`dynamic sort-key regression: ${scenarioOrder.slice(0, 12).join(",")}`);
}
parameters.getRange("B4:B10").values = weights.map((weight) => [weight]);
comparison.getRange("E5:E54").format.numberFormat = '"¥"#,##0';
comparison.getRange("H5:J54").format.numberFormat = '"¥"#,##0';
comparison.getRange("K5:Q54").format.numberFormat = "0";
comparison.getRange("R5:R54").format.numberFormat = "0.00";
comparison.getRange("A5:X54").format = {
  verticalAlignment: "top",
  wrapText: true,
  borders: { preset: "inside", style: "thin", color: color.border },
};
comparison.getRange("B5:B54").format.horizontalAlignment = "center";
comparison.getRange("E5:R54").format.horizontalAlignment = "right";
comparison.getRange("A5:A54").conditionalFormats.add("containsText", { text: "首做", format: { fill: color.tealLight, font: { bold: true, color: color.green } } });
comparison.getRange("R5:R54").conditionalFormats.add("colorScale", { colors: ["#FEE2E2", "#FEF3C7", "#DCFCE7"], thresholds: ["min", "50%", "max"] });
comparison.getRange("H5:J54").conditionalFormats.add("dataBar", { color: "#5EEAD4", gradient: true });
const comparisonTable = comparison.tables.add("A4:X54", true, "OpportunityComparison");
comparisonTable.style = "TableStyleMedium2";
comparisonTable.showFilterButton = true;
comparison.freezePanes.freezeRows(4);
comparison.freezePanes.freezeColumns(3);
const widths = [10, 6, 30, 16, 14, 8, 10, 13, 13, 13, 8, 8, 8, 8, 8, 8, 10, 10, 36, 48, 34, 52, 44, 13];
for (let i = 0; i < widths.length; i++) comparison.getRangeByIndexes(0, i, 54, 1).format.columnWidth = widths[i];
comparison.getRange("5:54").format.rowHeight = 56;

// Compact priority dashboard.
styleTitle(overview, overview.getRange("A1:H2"), "先做一个，不要同时开三条线");
overview.getRange("A3:H3").merge();
overview.getRange("A3:H3").values = [["优先级依据：结果可测、低成本、30 天付费、合法渠道、可回滚。前三并非收益保证，仍以首个付费试点为裁决。"]];
overview.getRange("A3:H3").format = { fill: color.grayLight, font: { color: color.gray, italic: true }, wrapText: true };
const cards = [
  ["A5:B5", "A6:B7", "项目总数", "=COUNTA('50项目对比'!$B$5:$B$54)", "0"],
  ["C5:D5", "C6:D7", "14 天内可验证", "=COUNTIF('50项目对比'!$G$5:$G$54,\"<=14\")", "0"],
  ["E5:F5", "E6:F7", "中性月营收中位数", "=MEDIAN('50项目对比'!$I$5:$I$54)", '"¥"#,##0'],
  ["G5:H5", "G6:H7", "启动成本上限中位数", "=MEDIAN('50项目对比'!$E$5:$E$54)", '"¥"#,##0'],
];
for (const [labelRange, valueRange, label, formula, format] of cards) {
  overview.getRange(labelRange).merge();
  overview.getRange(labelRange).values = [[label]];
  overview.getRange(labelRange).format = { fill: color.teal, font: { bold: true, color: color.white }, horizontalAlignment: "center", verticalAlignment: "center" };
  overview.getRange(valueRange).merge();
  overview.getRange(valueRange).formulas = [[formula]];
  overview.getRange(valueRange).format = { fill: color.tealLight, font: { bold: true, color: color.navy, size: 18 }, horizontalAlignment: "center", verticalAlignment: "center", numberFormat: format, borders: { preset: "outside", style: "thin", color: color.border } };
}
overview.getRange("A9:H9").merge();
overview.getRange("A9:H9").values = [["建议首做三项"]];
overview.getRange("A9:H9").format = { fill: color.navy, font: { bold: true, color: color.white, size: 14 } };
overview.getRange("A10:H10").values = [["顺序", "方法", "为什么稳", "成本上限", "验证天", "中性/月", "综合分", "文件"]];
styleHeader(overview.getRange("A10:H10"));
const topIds = [20, 1, 22];
const reasons = [
  "官方 Diagnostics 直接给出错误；修复是否通过可验收，不依赖流量承诺",
  "AI integration 需求上升；首响与路由可用历史线索回放，设置费+监控费",
  "测试订单可对账事件、币种和去重；结果是技术正确性而非模糊营销归因",
];
const topRows = topIds.map((id, i) => {
  const m = methods.find((x) => x.id === id);
  return [i + 1, m.title, reasons[i], maxCost(m.cost), validationDays(m), m.monthly[1], null, `methods/${String(m.id).padStart(2, "0")}-${m.slug}.md`];
});
overview.getRange("A11:H13").values = topRows;
for (let i = 0; i < topIds.length; i++) {
  const comparisonRow = comparisonRowById.get(topIds[i]);
  overview.getRange(`G${11 + i}`).formulas = [[`='50项目对比'!R${comparisonRow}`]];
}
overview.getRange("D11:F13").format.numberFormat = '"¥"#,##0';
overview.getRange("E11:E13").format.numberFormat = "0";
overview.getRange("G11:G13").format.numberFormat = "0.00";
overview.getRange("A11:H13").format = { wrapText: true, verticalAlignment: "top", borders: { preset: "inside", style: "thin", color: color.border } };
overview.getRange("A11:A13").format = { fill: color.amberLight, font: { bold: true, color: color.navy }, horizontalAlignment: "center" };
overview.getRange("A15:H15").merge();
overview.getRange("A15:H15").values = [["执行规则"]];
overview.getRange("A15:H15").format = { fill: color.navy, font: { bold: true, color: color.white, size: 14 } };
overview.getRange("A16:H20").merge(true);
overview.getRange("A16:H20").values = [
  ["1. 只选一个方法；通常 Day 20 前拿到已注资里程碑、平台净订单或已入账合法账单。方法48例外：Day20终稿/预售、Day27发行、Day30以至少5个不重复净付费购买裁决。"],
  ["2. 先验证 KYC、收款、权限和数据许可；任何失败都不靠虚假地区、抓取或群发解决。"],
  ["3. 所有收益是模型；用实际订单、工时、工具费、平台费、退款替换后再扩大。"],
  ["4. 支付、退款、删除、改价、公开回复、法律/医疗/金融判断始终保留人工批准。"],
  ["5. 30 天无付费、许可不清或贡献毛利低于 60%，缩窄、换细分或停止。"],
];
overview.getRange("A16:H20").format = { fill: color.grayLight, font: { color: color.navy }, wrapText: true, verticalAlignment: "center", borders: { preset: "inside", style: "thin", color: color.border } };
const overviewWidths = [8, 28, 54, 14, 10, 14, 12, 42];
for (let i = 0; i < overviewWidths.length; i++) overview.getRangeByIndexes(0, i, 21, 1).format.columnWidth = overviewWidths[i];
overview.getRange("11:13").format.rowHeight = 48;
overview.getRange("16:20").format.rowHeight = 28;
overview.freezePanes.freezeRows(3);

// Source ledger.
styleTitle(sourceSheet, sourceSheet.getRange("A1:E2"), "来源账本｜一手事实与使用边界");
sourceSheet.getRange("A3:E3").values = [["来源ID", "标题", "URL", "本报告采用事实", "局限/边界"]];
styleHeader(sourceSheet.getRange("A3:E3"));
const sourceRows = Object.entries(sources).map(([id, source]) => [id, source.title, source.url, source.fact, source.caveat]);
sourceSheet.getRangeByIndexes(3, 0, sourceRows.length, 5).values = sourceRows;
sourceSheet.getRangeByIndexes(3, 0, sourceRows.length, 5).format = { wrapText: true, verticalAlignment: "top", borders: { preset: "inside", style: "thin", color: color.border } };
const sourceTable = sourceSheet.tables.add(`A3:E${sourceRows.length + 3}`, true, "SourceLedger");
sourceTable.style = "TableStyleMedium2";
sourceTable.showFilterButton = true;
sourceSheet.getRange("A:A").format.columnWidth = 10;
sourceSheet.getRange("B:B").format.columnWidth = 34;
sourceSheet.getRange("C:C").format.columnWidth = 54;
sourceSheet.getRange("D:D").format.columnWidth = 58;
sourceSheet.getRange("E:E").format.columnWidth = 52;
sourceSheet.getRange(`4:${sourceRows.length + 3}`).format.rowHeight = 58;
sourceSheet.freezePanes.freezeRows(3);

await fs.mkdir(outputDir, { recursive: true });
const previewDir = path.join(outputDir, "previews");
await fs.mkdir(previewDir, { recursive: true });
const previews = [
  ["优先级", "A1:H20", "overview.png"],
  ["50项目对比", "A1:X15", "comparison.png"],
  ["评分参数", "A1:D14", "parameters.png"],
  ["来源", "A1:E16", "sources.png"],
];
for (const [sheetName, range, filename] of previews) {
  const preview = await workbook.render({ sheetName, range, scale: 1.25, format: "png" });
  await fs.writeFile(path.join(previewDir, filename), new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(outputDir, "comparison.xlsx"));

const inspect = await workbook.inspect({
  kind: "table",
  range: "优先级!A1:H20",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 8,
});
console.log(inspect.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);
console.log(JSON.stringify({ output: path.join(outputDir, "comparison.xlsx"), previews: previewDir, methods: methods.length, sources: sourceRows.length }));
