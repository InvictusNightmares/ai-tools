import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error("Usage: build_sub2api_group_token_usage.mjs <input-json> <output-xlsx>");
}

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const metadata = payload.metadata ?? {};
const summary = payload.summary ?? [];
const perGroup = payload.per_group ?? [];
const number = (value) => Number(value ?? 0);
const money = (value) => number(value);

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("汇总");
const groupSheet = workbook.worksheets.add("每个分组");

const navy = "#0F172A";
const slate = "#334155";
const headerFill = "#1E293B";
const lightFill = "#F8FAFC";
const borderColor = "#CBD5E1";
const totalFill = "#DCFCE7";
const totalText = "#14532D";

const formatTitle = (sheet, range, value) => {
  sheet.mergeCells(range);
  const title = sheet.getRange(range);
  title.values = [[value]];
  title.format.fill = navy;
  title.format.font = { bold: true, color: "#FFFFFF", size: 16 };
  title.format.rowHeight = 30;
  title.format.verticalAlignment = "center";
};

const formatNote = (sheet, range, value) => {
  sheet.mergeCells(range);
  const note = sheet.getRange(range);
  note.values = [[value]];
  note.format.fill = lightFill;
  note.format.font = { color: slate, italic: true, size: 10 };
  note.format.rowHeight = 24;
};

const formatHeader = (sheet, range) => {
  const header = sheet.getRange(range);
  header.format.fill = headerFill;
  header.format.font = { bold: true, color: "#FFFFFF", size: 10 };
  header.format.wrapText = true;
  header.format.rowHeight = 32;
  header.format.verticalAlignment = "center";
};

const formatTable = (sheet, range) => {
  const body = sheet.getRange(range);
  body.format.borders = { preset: "all", style: "thin", color: borderColor };
  body.format.verticalAlignment = "center";
};

const headers = [
  "服务器 / Server",
  "分组数 / Groups",
  "请求数 / Requests",
  "Input Token",
  "Output Token",
  "Cache Creation",
  "Cache Read",
  "Image Input",
  "Image Output",
  "Total Token",
  "Total含图片 / Total+Image",
  "Actual Cost",
];

formatTitle(summarySheet, "A1:L1", "Sub2API 分组 Token 用量汇总 / Group Token Usage Summary");
formatNote(
  summarySheet,
  "A2:L2",
  `统计范围 / Period: ${metadata.from} 至 ${metadata.to}；时区 / Timezone: ${metadata.timezone}；来源: 美西 qiyuan-us、东京 qiyuan-tokyo；按 usage_logs.group_id 归属`,
);
summarySheet.getRange("A4:L4").values = [headers];
formatHeader(summarySheet, "A4:L4");

const summaryStart = 5;
const summaryRows = summary.map((row) => [
  row.server,
  number(row.group_count),
  number(row.request_count),
  number(row.input_tokens),
  number(row.output_tokens),
  number(row.cache_creation_tokens),
  number(row.cache_read_tokens),
  number(row.image_input_tokens),
  number(row.image_output_tokens),
  null,
  null,
  money(row.actual_cost),
]);

if (summaryRows.length > 0) {
  const summaryEnd = summaryStart + summaryRows.length - 1;
  summarySheet.getRange(`A${summaryStart}:L${summaryEnd}`).values = summaryRows;
  summarySheet.getRange(`J${summaryStart}`).formulas = [[`=SUM(D${summaryStart}:G${summaryStart})`]];
  summarySheet.getRange(`J${summaryStart}:J${summaryEnd}`).fillDown();
  summarySheet.getRange(`K${summaryStart}`).formulas = [[`=J${summaryStart}+H${summaryStart}+I${summaryStart}`]];
  summarySheet.getRange(`K${summaryStart}:K${summaryEnd}`).fillDown();
  formatTable(summarySheet, `A4:L${summaryEnd}`);

  const totalRow = summaryEnd + 1;
  summarySheet.getRange(`A${totalRow}:L${totalRow}`).values = [[
    "合计 / Total", null, null, null, null, null, null, null, null, null, null, null,
  ]];
  for (const column of ["B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]) {
    summarySheet.getRange(`${column}${totalRow}`).formulas = [[`=SUM(${column}${summaryStart}:${column}${summaryEnd})`]];
  }
  summarySheet.getRange(`A${totalRow}:L${totalRow}`).format.fill = totalFill;
  summarySheet.getRange(`A${totalRow}:L${totalRow}`).format.font = { bold: true, color: totalText };
  summarySheet.getRange(`A${totalRow}:L${totalRow}`).format.borders = {
    preset: "all", style: "thin", color: borderColor,
  };
  summarySheet.tables.add(`A4:L${summaryEnd}`, true, "GroupUsageSummaryTable");
}

const groupHeaders = [
  "服务器 / Server",
  "分组 / Group",
  "Key数 / Keys",
  "请求数 / Requests",
  "Input Token",
  "Output Token",
  "Cache Creation",
  "Cache Read",
  "Image Input",
  "Image Output",
  "Total Token",
  "Total含图片 / Total+Image",
  "Actual Cost",
];

formatTitle(groupSheet, "A1:M1", "Sub2API 每个分组 Token 用量 / Per-Group Token Usage");
formatNote(
  groupSheet,
  "A2:M2",
  `统计范围 / Period: ${metadata.from} 至 ${metadata.to}；按请求次数从多到少排序；Key数为分组内有用量的去重 API Key 数`,
);
groupSheet.getRange("A4:M4").values = [groupHeaders];
formatHeader(groupSheet, "A4:M4");

const groupStart = 5;
const groupRows = perGroup.map((row) => [
  row.server,
  row.group_name,
  number(row.key_count),
  number(row.request_count),
  number(row.input_tokens),
  number(row.output_tokens),
  number(row.cache_creation_tokens),
  number(row.cache_read_tokens),
  number(row.image_input_tokens),
  number(row.image_output_tokens),
  null,
  null,
  money(row.actual_cost),
]);

if (groupRows.length > 0) {
  const groupEnd = groupStart + groupRows.length - 1;
  groupSheet.getRange(`A${groupStart}:M${groupEnd}`).values = groupRows;
  groupSheet.getRange(`K${groupStart}`).formulas = [[`=SUM(E${groupStart}:H${groupStart})`]];
  groupSheet.getRange(`K${groupStart}:K${groupEnd}`).fillDown();
  groupSheet.getRange(`L${groupStart}`).formulas = [[`=K${groupStart}+I${groupStart}+J${groupStart}`]];
  groupSheet.getRange(`L${groupStart}:L${groupEnd}`).fillDown();
  formatTable(groupSheet, `A4:M${groupEnd}`);

  const totalRow = groupEnd + 1;
  groupSheet.getRange(`A${totalRow}:M${totalRow}`).values = [[
    "合计 / Total", null, null, null, null, null, null, null, null, null, null, null, null,
  ]];
  for (const column of ["C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"]) {
    groupSheet.getRange(`${column}${totalRow}`).formulas = [[`=SUM(${column}${groupStart}:${column}${groupEnd})`]];
  }
  groupSheet.getRange(`A${totalRow}:M${totalRow}`).format.fill = totalFill;
  groupSheet.getRange(`A${totalRow}:M${totalRow}`).format.font = { bold: true, color: totalText };
  groupSheet.getRange(`A${totalRow}:M${totalRow}`).format.borders = {
    preset: "all", style: "thin", color: borderColor,
  };
  groupSheet.tables.add(`A4:M${groupEnd}`, true, "PerGroupUsageTable");
}

for (const sheet of [summarySheet, groupSheet]) {
  sheet.showGridLines = false;
  sheet.getUsedRange().format.font.name = "Aptos";
  sheet.getUsedRange().format.verticalAlignment = "center";
  sheet.freezePanes.freezeRows(4);
}

if (summaryRows.length > 0) {
  const summaryEnd = summaryStart + summaryRows.length - 1;
  summarySheet.getRange(`B${summaryStart}:K${summaryEnd + 1}`).format.numberFormat = "#,##0";
  summarySheet.getRange(`L${summaryStart}:L${summaryEnd + 1}`).format.numberFormat = '"$"#,##0.0000';
}
if (groupRows.length > 0) {
  const groupEnd = groupStart + groupRows.length - 1;
  groupSheet.getRange(`C${groupStart}:L${groupEnd + 1}`).format.numberFormat = "#,##0";
  groupSheet.getRange(`M${groupStart}:M${groupEnd + 1}`).format.numberFormat = '"$"#,##0.0000';
}

summarySheet.getRange("A1:A10").format.columnWidth = 14;
summarySheet.getRange("B1:B10").format.columnWidth = 13;
summarySheet.getRange("C1:K10").format.columnWidth = 16;
summarySheet.getRange("L1:L10").format.columnWidth = 14;
groupSheet.getRange("A1:A300").format.columnWidth = 14;
groupSheet.getRange("B1:B300").format.columnWidth = 24;
groupSheet.getRange("C1:L300").format.columnWidth = 16;
groupSheet.getRange("M1:M300").format.columnWidth = 14;

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const summaryInspect = await workbook.inspect({
  kind: "table",
  range: `汇总!A1:L${Math.min(summaryStart + summaryRows.length, 12)}`,
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 12,
  tableMaxCellChars: 80,
});
console.log(summaryInspect.ndjson);

const groupInspect = await workbook.inspect({
  kind: "table",
  range: `每个分组!A1:M${Math.min(groupStart + groupRows.length, 18)}`,
  include: "values,formulas",
  tableMaxRows: 18,
  tableMaxCols: 13,
  tableMaxCellChars: 80,
});
console.log(groupInspect.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const previewDir = "/private/tmp/sub2api-group-token-usage-preview";
await fs.mkdir(previewDir, { recursive: true });
for (const [sheetName, range, fileName] of [
  ["汇总", `A1:L${Math.min(summaryStart + summaryRows.length + 1, 20)}`, "summary.png"],
  ["每个分组", `A1:M${Math.min(groupStart + groupRows.length + 1, 30)}`, "per-group.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.3, format: "png" });
  await fs.writeFile(`${previewDir}/${fileName}`, new Uint8Array(await preview.arrayBuffer()));
}
