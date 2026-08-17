import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = "/Users/invictus/Github/ai-tools/outputs/2026-08-17-token-usage/token_usage_trend_2026-08-03_to_2026-08-13.xlsx";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));

const tokyo = workbook.worksheets.getItem("Token趋势");
tokyo.getRange("A1").values = [["东京 Token 使用趋势 / Tokyo Token Usage Trend"]];
tokyo.getRange("A2").values = [["东京 / Tokyo；统计范围 / Period: 2026-08-03 至 2026-08-13；来源 / Source: http://8.216.44.189:8080/admin/dashboard"]];

const westRows = [
  [new Date("2026-08-03"), 182470000, 14370000, 0, 2310000000, 0.927, 2430, 2430],
  [new Date("2026-08-04"), 196570000, 14640000, 0, 2990000000, 0.938, 2750, 2750],
  [new Date("2026-08-05"), 177570000, 11840000, 0, 2430000000, 0.932, 2270, 2270],
  [new Date("2026-08-06"), 208640000, 16170000, 0, 2820000000, 0.931, 2770, 2770],
  [new Date("2026-08-07"), 150060000, 12060000, 84200, 2230000000, 0.937, 2150, 2150],
  [new Date("2026-08-08"), 20400000, 1700000, 0, 373910000, 0.948, 336.07, 336.07],
  [new Date("2026-08-09"), 29930000, 2490000, 0, 696800000, 0.959, 585.57, 585.57],
  [new Date("2026-08-10"), 154240000, 12720000, 0, 2430000000, 0.940, 2270, 2270],
  [new Date("2026-08-11"), 228450000, 18730000, 0, 3790000000, 0.943, 3270, 3270],
  [new Date("2026-08-12"), 398020000, 14580000, 0, 2330000000, 0.854, 3320, 3320],
  [new Date("2026-08-13"), 398540000, 15490000, 0, 3060000000, 0.885, 3740, 3740],
];

const sheet = workbook.worksheets.add("美西趋势");
sheet.showGridLines = false;
sheet.mergeCells("A1:I1");
sheet.getRange("A1").values = [["美西 Token 使用趋势 / US West Token Usage Trend"]];
sheet.getRange("A1:I1").format.fill = "#0F172A";
sheet.getRange("A1:I1").format.font = { bold: true, color: "#FFFFFF", size: 16 };
sheet.getRange("A1:I1").format.rowHeight = 30;

sheet.mergeCells("A2:I2");
sheet.getRange("A2").values = [["美西 / US West；统计范围 / Period: 2026-08-03 至 2026-08-13；来源 / Source: http://106.14.254.110:9880/admin/dashboard"]];
sheet.getRange("A2:I2").format.font = { color: "#475569", italic: true, size: 10 };

sheet.getRange("A4:H4").values = [[
  "统计天数 / Days", null,
  "总 Token / Total Tokens", null,
  "平均命中率 / Avg Hit Rate", null,
  "Cache Read 合计 / Total", null,
]];
sheet.getRange("B4").formulas = [["=COUNTA(A8:A18)"]];
sheet.getRange("D4").formulas = [["=SUM(G8:G18)"]];
sheet.getRange("F4").formulas = [["=AVERAGE(F8:F18)"]];
sheet.getRange("H4").formulas = [["=SUM(E8:E18)"]];
sheet.getRange("A4:H4").format.fill = "#E2E8F0";
sheet.getRange("A4:H4").format.font = { bold: true, color: "#0F172A", size: 10 };
sheet.getRange("B4").format.numberFormat = "#,##0";
sheet.getRange("D4").format.numberFormat = "#,##0";
sheet.getRange("F4").format.numberFormat = "0.0%";
sheet.getRange("H4").format.numberFormat = "#,##0";

sheet.mergeCells("A5:I5");
sheet.getRange("A5").values = [["口径说明 / Definition: Token 数值按后台图表提示中的 B/M/K 单位还原为绝对数量；Actual、Standard 为同一图表提示中的 USD 值。"]];
sheet.getRange("A5:I5").format.fill = "#F8FAFC";
sheet.getRange("A5:I5").format.font = { color: "#475569", size: 10 };

sheet.getRange("A7:I7").values = [[
  "日期 / Date",
  "Input / 输入",
  "Output / 输出",
  "Cache Creation / 缓存创建",
  "Cache Read / 缓存读取",
  "Cache Hit Rate / 缓存命中率",
  "Total Token / 总 Token",
  "Actual / 实际",
  "Standard / 标准",
]];
sheet.getRange("A7:I7").format.fill = "#1E293B";
sheet.getRange("A7:I7").format.font = { bold: true, color: "#FFFFFF" };
sheet.getRange("A7:I7").format.wrapText = true;
sheet.getRange("A7:I7").format.rowHeight = 32;

sheet.getRange("A8:I18").values = westRows.map((row) => [row[0], row[1], row[2], row[3], row[4], row[5], null, row[6], row[7]]);
sheet.getRange("G8:G18").formulas = westRows.map((_, index) => [`=SUM(B${index + 8}:E${index + 8})`]);

sheet.getRange("A19").values = [["合计 / Average"]];
sheet.getRange("B19:E19").formulas = [["=SUM(B8:B18)", "=SUM(C8:C18)", "=SUM(D8:D18)", "=SUM(E8:E18)"]];
sheet.getRange("F19").formulas = [["=AVERAGE(F8:F18)"]];
sheet.getRange("G19").formulas = [["=SUM(G8:G18)"]];
sheet.getRange("H19:I19").formulas = [["=SUM(H8:H18)", "=SUM(I8:I18)"]];

sheet.getRange("A8:A18").format.numberFormat = "yyyy-mm-dd";
sheet.getRange("B8:E19").format.numberFormat = "#,##0";
sheet.getRange("F8:F19").format.numberFormat = "0.0%";
sheet.getRange("G8:G19").format.numberFormat = "#,##0";
sheet.getRange("H8:I19").format.numberFormat = '"$"#,##0.00';
sheet.getRange("A19:I19").format.fill = "#DCFCE7";
sheet.getRange("A19:I19").format.font = { bold: true, color: "#14532D" };
sheet.getRange("A7:I19").format.borders = { preset: "all", style: "thin", color: "#CBD5E1" };

const table = sheet.tables.add("A7:I18", true, "WestTokenTrendTable");
table.showFilterButton = true;

sheet.getRange("K7:L12").values = [
  ["English", "中文"],
  ["Input", "输入"],
  ["Output", "输出"],
  ["Cache Creation", "缓存创建"],
  ["Cache Read", "缓存读取"],
  ["Cache Hit Rate", "缓存命中率"],
];
sheet.getRange("K7:L7").format.fill = "#1E293B";
sheet.getRange("K7:L7").format.font = { bold: true, color: "#FFFFFF" };
sheet.getRange("K8:L12").format.fill = "#F8FAFC";
sheet.getRange("K7:L12").format.borders = { preset: "all", style: "thin", color: "#CBD5E1" };

sheet.getRange("A1:L19").format.font.name = "Aptos";
sheet.getRange("A1:L19").format.verticalAlignment = "center";
sheet.getRange("A1:L19").format.autofitColumns();
sheet.getRange("A1:A19").format.columnWidth = 16;
sheet.getRange("B1:D19").format.columnWidth = 18;
sheet.getRange("E1:E19").format.columnWidth = 25;
sheet.getRange("F1:F19").format.columnWidth = 23;
sheet.getRange("G1:G19").format.columnWidth = 25;
sheet.getRange("H1:I19").format.columnWidth = 14;
sheet.getRange("J1:J19").format.columnWidth = 3;
sheet.getRange("K1:L19").format.columnWidth = 18;
sheet.getRange("A5:I5").format.rowHeight = 24;
sheet.freezePanes.freezeRows(7);

const outputDir = "/Users/invictus/Github/ai-tools/outputs/2026-08-17-token-usage";
const tokyoPreview = await workbook.render({ sheetName: "Token趋势", range: "A1:L19", scale: 1.5, format: "png" });
await fs.writeFile(`${outputDir}/token_usage_tokyo_preview.png`, new Uint8Array(await tokyoPreview.arrayBuffer()));
const westPreview = await workbook.render({ sheetName: "美西趋势", range: "A1:L19", scale: 1.5, format: "png" });
await fs.writeFile(`${outputDir}/token_usage_west_preview.png`, new Uint8Array(await westPreview.arrayBuffer()));

const values = await workbook.inspect({
  kind: "table",
  range: "美西趋势!A1:L19",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 12,
  tableMaxCellChars: 80,
});
console.log(values.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(workbookPath);
console.log(`SAVED ${workbookPath}`);
