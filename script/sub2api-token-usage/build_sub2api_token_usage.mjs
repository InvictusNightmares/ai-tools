import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error("Usage: build_sub2api_token_usage.mjs <input-json> <output-xlsx>");
}

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const metadata = payload.metadata ?? {};
const daily = payload.daily ?? [];
const perKey = payload.per_key ?? [];

const number = (value) => Number(value ?? 0);
const dateValue = (value) => new Date(`${value}T00:00:00Z`);
const money = (value) => number(value);

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("汇总");
const keySheet = workbook.worksheets.add("每个Key");

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

const formatTableRange = (sheet, range) => {
  const body = sheet.getRange(range);
  body.format.borders = { preset: "all", style: "thin", color: borderColor };
  body.format.verticalAlignment = "center";
};

const summaryHeaders = [
  "服务器 / Server",
  "日期 / Date",
  "用户数 / Users",
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

formatTitle(summarySheet, "A1:N1", "Sub2API Token 用量汇总 / Token Usage Summary");
formatNote(
  summarySheet,
  "A2:N2",
  `统计范围 / Period: ${metadata.from} 至 ${metadata.to}；时区 / Timezone: ${metadata.timezone}；来源: 美西 qiyuan-us、东京 qiyuan-tokyo`,
);
summarySheet.getRange("A4:N4").values = [summaryHeaders];
formatHeader(summarySheet, "A4:N4");

const summaryStart = 5;
const summaryRows = daily.map((row) => [
  row.server,
  dateValue(row.usage_date),
  number(row.user_count),
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
if (summaryRows.length > 0) {
  const summaryEnd = summaryStart + summaryRows.length - 1;
  summarySheet.getRange(`A${summaryStart}:N${summaryEnd}`).values = summaryRows;
  summarySheet.getRange(`L${summaryStart}`).formulas = [[`=SUM(F${summaryStart}:I${summaryStart})`]];
  summarySheet.getRange(`L${summaryStart}:L${summaryEnd}`).fillDown();
  summarySheet.getRange(`M${summaryStart}`).formulas = [[`=L${summaryStart}+J${summaryStart}+K${summaryStart}`]];
  summarySheet.getRange(`M${summaryStart}:M${summaryEnd}`).fillDown();
  formatTableRange(summarySheet, `A4:N${summaryEnd}`);

  const totalRow = summaryEnd + 1;
  summarySheet.getRange(`A${totalRow}:N${totalRow}`).values = [[
    "合计 / Total",
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
  ]];
  for (const column of ["C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N"]) {
    summarySheet.getRange(`${column}${totalRow}`).formulas = [[`=SUM(${column}${summaryStart}:${column}${summaryEnd})`]];
  }
  summarySheet.getRange(`A${totalRow}:N${totalRow}`).format.fill = totalFill;
  summarySheet.getRange(`A${totalRow}:N${totalRow}`).format.font = { bold: true, color: totalText };
  summarySheet.getRange(`A${totalRow}:N${totalRow}`).format.borders = {
    preset: "all",
    style: "thin",
    color: borderColor,
  };
  summarySheet.tables.add(`A4:N${summaryEnd}`, true, "DailyTokenSummaryTable");
}

const keyHeaders = [
  "服务器 / Server",
  "Key名称 / Key Name",
  "用户 / User",
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

formatTitle(keySheet, "A1:M1", "Sub2API 每个 API Key 用量 / Per-Key Usage");
formatNote(
  keySheet,
  "A2:M2",
  `统计范围 / Period: ${metadata.from} 至 ${metadata.to}；按请求次数从多到少排序；API Key 密文未读取或输出`,
);
keySheet.getRange("A4:M4").values = [keyHeaders];
formatHeader(keySheet, "A4:M4");

const keyStart = 5;
const keyRows = perKey.map((row) => [
  row.server,
  row.api_key_name,
  row.user_label,
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
if (keyRows.length > 0) {
  const keyEnd = keyStart + keyRows.length - 1;
  keySheet.getRange(`A${keyStart}:M${keyEnd}`).values = keyRows;
  keySheet.getRange(`K${keyStart}`).formulas = [[`=SUM(E${keyStart}:H${keyStart})`]];
  keySheet.getRange(`K${keyStart}:K${keyEnd}`).fillDown();
  keySheet.getRange(`L${keyStart}`).formulas = [[`=K${keyStart}+I${keyStart}+J${keyStart}`]];
  keySheet.getRange(`L${keyStart}:L${keyEnd}`).fillDown();
  formatTableRange(keySheet, `A4:M${keyEnd}`);
  keySheet.tables.add(`A4:M${keyEnd}`, true, "PerKeyUsageTable");
}

for (const sheet of [summarySheet, keySheet]) {
  sheet.showGridLines = false;
  sheet.getUsedRange().format.font.name = "Aptos";
  sheet.getUsedRange().format.verticalAlignment = "center";
  sheet.freezePanes.freezeRows(4);
}

if (summaryRows.length > 0) {
  const summaryEnd = summaryStart + summaryRows.length - 1;
  summarySheet.getRange(`B${summaryStart}:B${summaryEnd}`).format.numberFormat = "yyyy-mm-dd";
  summarySheet.getRange(`C${summaryStart}:M${summaryEnd + 1}`).format.numberFormat = "#,##0";
  summarySheet.getRange(`N${summaryStart}:N${summaryEnd + 1}`).format.numberFormat = '"$"#,##0.0000';
}
if (keyRows.length > 0) {
  const keyEnd = keyStart + keyRows.length - 1;
  keySheet.getRange(`D${keyStart}:L${keyEnd}`).format.numberFormat = "#,##0";
  keySheet.getRange(`M${keyStart}:M${keyEnd}`).format.numberFormat = '"$"#,##0.0000';
}

summarySheet.getRange("A1:A200").format.columnWidth = 14;
summarySheet.getRange("B1:B200").format.columnWidth = 14;
summarySheet.getRange("C1:E200").format.columnWidth = 13;
summarySheet.getRange("F1:M200").format.columnWidth = 16;
summarySheet.getRange("N1:N200").format.columnWidth = 14;
keySheet.getRange("A1:A300").format.columnWidth = 14;
keySheet.getRange("B1:B300").format.columnWidth = 24;
keySheet.getRange("C1:C300").format.columnWidth = 16;
keySheet.getRange("D1:L300").format.columnWidth = 16;
keySheet.getRange("M1:M300").format.columnWidth = 14;

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const summaryInspect = await workbook.inspect({
  kind: "table",
  range: `汇总!A1:N${Math.min(summaryStart + summaryRows.length, 12)}`,
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 14,
  tableMaxCellChars: 80,
});
console.log(summaryInspect.ndjson);

const keyInspect = await workbook.inspect({
  kind: "table",
  range: `每个Key!A1:M${Math.min(keyStart + perKey.length, 12)}`,
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 13,
  tableMaxCellChars: 80,
});
console.log(keyInspect.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const previewDir = "/private/tmp/sub2api-token-usage-preview";
await fs.mkdir(previewDir, { recursive: true });
const summaryPreview = await workbook.render({
  sheetName: "汇总",
  range: `A1:N${Math.min(summaryStart + summaryRows.length + 1, 30)}`,
  scale: 1.4,
  format: "png",
});
await fs.writeFile(
  `${previewDir}/summary.png`,
  new Uint8Array(await summaryPreview.arrayBuffer()),
);
const keyPreview = await workbook.render({
  sheetName: "每个Key",
  range: `A1:M${Math.min(keyStart + perKey.length, 30)}`,
  scale: 1.2,
  format: "png",
});
await fs.writeFile(
  `${previewDir}/per-key.png`,
  new Uint8Array(await keyPreview.arrayBuffer()),
);
console.log(`SAVED ${outputPath}`);
