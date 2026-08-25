import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error(
    "Usage: build_sub2api_daily_person_token_usage.mjs <input-json> <output-xlsx>",
  );
}

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const metadata = payload.metadata ?? {};
const summary = payload.summary ?? [];
const perGroup = payload.per_group ?? [];
const perPerson = payload.per_person ?? [];
const number = (value) => Number(value ?? 0);

const serverStatus = (metadata.servers ?? [])
  .map(
    (server) =>
      server.name + ":" + (server.status === "ok" ? "正常" : "失败"),
  )
  .join("；");

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("汇总");
const groupSheet = workbook.worksheets.add("每个分组");
const personSheet = workbook.worksheets.add("人员使用排行榜");

const colors = {
  navy: "#0F172A",
  header: "#1E293B",
  slate: "#334155",
  muted: "#64748B",
  white: "#FFFFFF",
  note: "#F8FAFC",
  stripe: "#EFF6FF",
  border: "#CBD5E1",
  totalFill: "#DCFCE7",
  totalText: "#14532D",
};

function formatTitle(sheet, range, value) {
  sheet.mergeCells(range);
  const cell = sheet.getRange(range);
  cell.values = [[value]];
  cell.format.fill = colors.navy;
  cell.format.font = { bold: true, color: colors.white, size: 16 };
  cell.format.rowHeight = 32;
  cell.format.verticalAlignment = "center";
}

function formatNote(sheet, range, value) {
  sheet.mergeCells(range);
  const cell = sheet.getRange(range);
  cell.values = [[value]];
  cell.format.fill = colors.note;
  cell.format.font = { color: colors.slate, italic: true, size: 10 };
  cell.format.wrapText = true;
  cell.format.rowHeight = 46;
  cell.format.verticalAlignment = "center";
}

function formatHeader(sheet, range) {
  const header = sheet.getRange(range);
  header.format.fill = colors.header;
  header.format.font = { bold: true, color: colors.white, size: 10 };
  header.format.wrapText = true;
  header.format.rowHeight = 34;
  header.format.verticalAlignment = "center";
  header.format.horizontalAlignment = "center";
  header.format.borders = {
    preset: "all",
    style: "thin",
    color: colors.border,
  };
}

function formatRows(sheet, firstRow, lastRow, lastColumn) {
  if (lastRow < firstRow) return;
  for (let row = firstRow; row <= lastRow; row += 1) {
    const range = sheet.getRange("A" + row + ":" + lastColumn + row);
    if ((row - firstRow) % 2 === 1) {
      range.format.fill = colors.stripe;
    }
    range.format.rowHeight = 23;
  }
  const body = sheet.getRange(
    "A" + firstRow + ":" + lastColumn + lastRow,
  );
  body.format.borders = {
    preset: "all",
    style: "thin",
    color: colors.border,
  };
  body.format.verticalAlignment = "center";
}

function formatTotal(sheet, range) {
  const total = sheet.getRange(range);
  total.format.fill = colors.totalFill;
  total.format.font = { bold: true, color: colors.totalText };
  total.format.rowHeight = 25;
  total.format.borders = {
    preset: "all",
    style: "thin",
    color: colors.border,
  };
}

function formatNoData(sheet, range, value) {
  sheet.mergeCells(range);
  const cell = sheet.getRange(range);
  cell.values = [[value]];
  cell.format.fill = colors.note;
  cell.format.font = { italic: true, color: colors.muted };
  cell.format.rowHeight = 28;
  cell.format.horizontalAlignment = "center";
  cell.format.verticalAlignment = "center";
}

function fillFormula(sheet, column, firstRow, lastRow, formula) {
  if (lastRow < firstRow) return;
  sheet.getRange(column + firstRow).formulas = [[formula(firstRow)]];
  if (lastRow > firstRow) {
    sheet
      .getRange(column + firstRow + ":" + column + lastRow)
      .fillDown();
  }
}

const baseNote =
  "统计范围: " +
  metadata.from +
  " 至 " +
  metadata.to +
  "；时区: " +
  metadata.timezone +
  "；节点: " +
  serverStatus;

const summaryHeaders = [
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
formatTitle(summarySheet, "A1:L1", "Sub2API Token 使用汇总");
formatNote(summarySheet, "A2:L2", baseNote);
summarySheet.getRange("A4:L4").values = [summaryHeaders];
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
  number(row.actual_cost),
]);
let summaryEnd = summaryStart - 1;
let summaryTotalRow = summaryStart;
if (summaryRows.length > 0) {
  summaryEnd = summaryStart + summaryRows.length - 1;
  summaryTotalRow = summaryEnd + 1;
  summarySheet.getRange("A" + summaryStart + ":L" + summaryEnd).values =
    summaryRows;
  fillFormula(
    summarySheet,
    "J",
    summaryStart,
    summaryEnd,
    (row) => "=SUM(D" + row + ":G" + row + ")",
  );
  fillFormula(
    summarySheet,
    "K",
    summaryStart,
    summaryEnd,
    (row) => "=J" + row + "+H" + row + "+I" + row,
  );
  formatRows(summarySheet, summaryStart, summaryEnd, "L");
  summarySheet.tables.add(
    "A4:L" + summaryEnd,
    true,
    "ServerUsageSummaryTable",
  );
  summarySheet.getRange("A" + summaryTotalRow + ":L" + summaryTotalRow).values =
    [[
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
    ]];
  for (const column of ["B", "C", "D", "E", "F", "G", "H", "I", "L"]) {
    summarySheet.getRange(column + summaryTotalRow).formulas = [
      ["=SUM(" + column + summaryStart + ":" + column + summaryEnd + ")"],
    ];
  }
  summarySheet.getRange("J" + summaryTotalRow).formulas = [
    ["=SUM(D" + summaryTotalRow + ":G" + summaryTotalRow + ")"],
  ];
  summarySheet.getRange("K" + summaryTotalRow).formulas = [
    [
      "=J" +
        summaryTotalRow +
        "+H" +
        summaryTotalRow +
        "+I" +
        summaryTotalRow,
    ],
  ];
  formatTotal(summarySheet, "A" + summaryTotalRow + ":L" + summaryTotalRow);
} else {
  formatNoData(summarySheet, "A5:L5", "所选日期范围无用量数据");
}

const groupHeaders = [
  "服务器 / Server",
  "分组 / Group",
  "Key数 / Keys",
  "请求数 / Requests",
  "平均请求数 / Avg Requests",
  "Input Token",
  "Output Token",
  "Cache Creation",
  "Cache Read",
  "Image Input",
  "Image Output",
  "Total Token",
  "平均Token / Avg Token",
  "Total含图片 / Total+Image",
  "Actual Cost",
];
formatTitle(groupSheet, "A1:O1", "Sub2API 每个业务组 Token 使用量");
formatNote(
  groupSheet,
  "A2:O2",
  baseNote + "；按 Total Token 降序。",
);
groupSheet.getRange("A4:O4").values = [groupHeaders];
formatHeader(groupSheet, "A4:O4");

const groupStart = 5;
const groupRows = perGroup.map((row) => [
  row.server,
  row.business_group,
  number(row.key_count),
  number(row.request_count),
  null,
  number(row.input_tokens),
  number(row.output_tokens),
  number(row.cache_creation_tokens),
  number(row.cache_read_tokens),
  number(row.image_input_tokens),
  number(row.image_output_tokens),
  null,
  null,
  null,
  number(row.actual_cost),
]);
let groupEnd = groupStart - 1;
let groupTotalRow = groupStart;
if (groupRows.length > 0) {
  groupEnd = groupStart + groupRows.length - 1;
  groupTotalRow = groupEnd + 1;
  groupSheet.getRange("A" + groupStart + ":O" + groupEnd).values = groupRows;
  fillFormula(
    groupSheet,
    "E",
    groupStart,
    groupEnd,
    (row) => "=IFERROR(D" + row + "/C" + row + ",0)",
  );
  fillFormula(
    groupSheet,
    "L",
    groupStart,
    groupEnd,
    (row) => "=SUM(F" + row + ":I" + row + ")",
  );
  fillFormula(
    groupSheet,
    "M",
    groupStart,
    groupEnd,
    (row) => "=IFERROR(L" + row + "/C" + row + ",0)",
  );
  fillFormula(
    groupSheet,
    "N",
    groupStart,
    groupEnd,
    (row) => "=L" + row + "+J" + row + "+K" + row,
  );
  formatRows(groupSheet, groupStart, groupEnd, "O");
  groupSheet.tables.add("A4:O" + groupEnd, true, "BusinessGroupUsageTable");
  groupSheet.getRange("A" + groupTotalRow + ":O" + groupTotalRow).values = [[
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
    null,
  ]];
  for (const column of ["C", "D", "F", "G", "H", "I", "J", "K", "O"]) {
    groupSheet.getRange(column + groupTotalRow).formulas = [
      ["=SUM(" + column + groupStart + ":" + column + groupEnd + ")"],
    ];
  }
  groupSheet.getRange("E" + groupTotalRow).formulas = [
    ["=IFERROR(D" + groupTotalRow + "/C" + groupTotalRow + ",0)"],
  ];
  groupSheet.getRange("L" + groupTotalRow).formulas = [
    ["=SUM(F" + groupTotalRow + ":I" + groupTotalRow + ")"],
  ];
  groupSheet.getRange("M" + groupTotalRow).formulas = [
    ["=IFERROR(L" + groupTotalRow + "/C" + groupTotalRow + ",0)"],
  ];
  groupSheet.getRange("N" + groupTotalRow).formulas = [
    [
      "=L" +
        groupTotalRow +
        "+J" +
        groupTotalRow +
        "+K" +
        groupTotalRow,
    ],
  ];
  formatTotal(groupSheet, "A" + groupTotalRow + ":O" + groupTotalRow);
} else {
  formatNoData(groupSheet, "A5:O5", "所选日期范围无业务组用量数据");
}

const personHeaders = [
  "排名 / Rank",
  "服务器 / Server",
  "分组 / Group",
  "人员 / Person",
  "Key数 / Keys",
  "请求数 / Requests",
  "平均请求数 / Avg Requests",
  "Input Token",
  "Output Token",
  "Cache Creation",
  "Cache Read",
  "Image Input",
  "Image Output",
  "Total Token",
  "平均Token / Avg Token",
  "Total含图片 / Total+Image",
  "Actual Cost",
];
formatTitle(personSheet, "A1:Q1", "Sub2API 人员 Token 使用排行榜");
formatNote(
  personSheet,
  "A2:Q2",
  baseNote + "；按 Total Token 从大到小排列。",
);
personSheet.getRange("A4:Q4").values = [personHeaders];
formatHeader(personSheet, "A4:Q4");

const personStart = 5;
const personRows = perPerson.map((row) => [
  number(row.rank),
  row.servers,
  row.business_group,
  row.person_name,
  number(row.key_count),
  number(row.request_count),
  null,
  number(row.input_tokens),
  number(row.output_tokens),
  number(row.cache_creation_tokens),
  number(row.cache_read_tokens),
  number(row.image_input_tokens),
  number(row.image_output_tokens),
  null,
  null,
  null,
  number(row.actual_cost),
]);
let personEnd = personStart - 1;
let personTotalRow = personStart;
if (personRows.length > 0) {
  personEnd = personStart + personRows.length - 1;
  personTotalRow = personEnd + 1;
  personSheet.getRange("A" + personStart + ":Q" + personEnd).values =
    personRows;
  fillFormula(
    personSheet,
    "G",
    personStart,
    personEnd,
    (row) => "=IFERROR(F" + row + "/E" + row + ",0)",
  );
  fillFormula(
    personSheet,
    "N",
    personStart,
    personEnd,
    (row) => "=SUM(H" + row + ":K" + row + ")",
  );
  fillFormula(
    personSheet,
    "O",
    personStart,
    personEnd,
    (row) => "=IFERROR(N" + row + "/E" + row + ",0)",
  );
  fillFormula(
    personSheet,
    "P",
    personStart,
    personEnd,
    (row) => "=N" + row + "+L" + row + "+M" + row,
  );
  formatRows(personSheet, personStart, personEnd, "Q");
  personSheet.tables.add("A4:Q" + personEnd, true, "PersonUsageRankingTable");
  personSheet.getRange("A" + personTotalRow + ":Q" + personTotalRow).values =
    [[
      null,
      null,
      null,
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
  for (const column of ["E", "F", "H", "I", "J", "K", "L", "M", "Q"]) {
    personSheet.getRange(column + personTotalRow).formulas = [
      ["=SUM(" + column + personStart + ":" + column + personEnd + ")"],
    ];
  }
  personSheet.getRange("G" + personTotalRow).formulas = [
    ["=IFERROR(F" + personTotalRow + "/E" + personTotalRow + ",0)"],
  ];
  personSheet.getRange("N" + personTotalRow).formulas = [
    ["=SUM(H" + personTotalRow + ":K" + personTotalRow + ")"],
  ];
  personSheet.getRange("O" + personTotalRow).formulas = [
    ["=IFERROR(N" + personTotalRow + "/E" + personTotalRow + ",0)"],
  ];
  personSheet.getRange("P" + personTotalRow).formulas = [
    [
      "=N" +
        personTotalRow +
        "+L" +
        personTotalRow +
        "+M" +
        personTotalRow,
    ],
  ];
  formatTotal(personSheet, "A" + personTotalRow + ":Q" + personTotalRow);
} else {
  formatNoData(personSheet, "A5:Q5", "所选日期范围无人员用量数据");
}

for (const sheet of [summarySheet, groupSheet, personSheet]) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(4);
  const used = sheet.getUsedRange();
  used.format.font.name = "Aptos";
  used.format.verticalAlignment = "center";
}

const summaryLastRow = Math.max(summaryTotalRow, 5);
summarySheet
  .getRange("B" + summaryStart + ":K" + summaryLastRow)
  .format.numberFormat = "#,##0";
summarySheet
  .getRange("L" + summaryStart + ":L" + summaryLastRow)
  .format.numberFormat = '"$"#,##0.0000';
summarySheet.getRange("A1:A" + summaryLastRow).format.columnWidth = 13;
summarySheet.getRange("B1:C" + summaryLastRow).format.columnWidth = 14;
summarySheet.getRange("D1:K" + summaryLastRow).format.columnWidth = 16;
summarySheet.getRange("L1:L" + summaryLastRow).format.columnWidth = 14;

const groupLastRow = Math.max(groupTotalRow, 5);
groupSheet
  .getRange("C" + groupStart + ":N" + groupLastRow)
  .format.numberFormat = "#,##0";
groupSheet
  .getRange("O" + groupStart + ":O" + groupLastRow)
  .format.numberFormat = '"$"#,##0.0000';
groupSheet.getRange("A1:A" + groupLastRow).format.columnWidth = 13;
groupSheet.getRange("B1:B" + groupLastRow).format.columnWidth = 16;
groupSheet.getRange("C1:E" + groupLastRow).format.columnWidth = 14;
groupSheet.getRange("F1:N" + groupLastRow).format.columnWidth = 16;
groupSheet.getRange("O1:O" + groupLastRow).format.columnWidth = 14;

const personLastRow = Math.max(personTotalRow, 5);
personSheet
  .getRange("A" + personStart + ":P" + personLastRow)
  .format.numberFormat = "#,##0";
personSheet
  .getRange("Q" + personStart + ":Q" + personLastRow)
  .format.numberFormat = '"$"#,##0.0000';
personSheet.getRange("A1:A" + personLastRow).format.columnWidth = 10;
personSheet.getRange("B1:B" + personLastRow).format.columnWidth = 13;
personSheet.getRange("C1:D" + personLastRow).format.columnWidth = 16;
personSheet.getRange("E1:G" + personLastRow).format.columnWidth = 14;
personSheet.getRange("H1:P" + personLastRow).format.columnWidth = 16;
personSheet.getRange("Q1:Q" + personLastRow).format.columnWidth = 14;

const summaryInspect = await workbook.inspect({
  kind: "table",
  range: "汇总!A1:L" + Math.min(summaryLastRow, 16),
  include: "values,formulas",
  tableMaxRows: 16,
  tableMaxCols: 12,
  tableMaxCellChars: 120,
});
console.log(summaryInspect.ndjson);

const groupInspect = await workbook.inspect({
  kind: "table",
  range: "每个分组!A1:O" + Math.min(groupLastRow, 24),
  include: "values,formulas",
  tableMaxRows: 24,
  tableMaxCols: 15,
  tableMaxCellChars: 100,
});
console.log(groupInspect.ndjson);

const personInspect = await workbook.inspect({
  kind: "table",
  range: "人员使用排行榜!A1:Q" + Math.min(personLastRow, 30),
  include: "values,formulas",
  tableMaxRows: 30,
  tableMaxCols: 17,
  tableMaxCellChars: 100,
});
console.log(personInspect.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const previewDir = "/private/tmp/sub2api-daily-person-token-usage-preview";
await fs.mkdir(previewDir, { recursive: true });
const previews = [
  [summarySheet, "汇总", "A1:L" + Math.min(summaryLastRow, 16), "summary.png"],
  [
    groupSheet,
    "每个分组",
    "A1:O" + Math.min(groupLastRow, 24),
    "per-group.png",
  ],
  [
    personSheet,
    "人员使用排行榜",
    "A1:Q" + Math.min(personLastRow, 32),
    "per-person.png",
  ],
];
for (const [, sheetName, range, fileName] of previews) {
  const preview = await workbook.render({
    sheetName,
    range,
    scale: 1.2,
    format: "png",
  });
  await fs.writeFile(
    path.join(previewDir, fileName),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log("SAVED " + outputPath);
