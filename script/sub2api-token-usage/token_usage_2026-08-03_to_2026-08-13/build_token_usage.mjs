import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "/Users/invictus/Github/ai-tools/outputs/2026-08-17-token-usage";
await fs.mkdir(outputDir, { recursive: true });

const rows = [
  [new Date("2026-08-03"), 184250000, 12170000, 0, 2020000000, 0.916, 2320, 2320],
  [new Date("2026-08-04"), 178780000, 11070000, 0, 2540000000, 0.934, 2600, 2600],
  [new Date("2026-08-05"), 138100000, 8790000, 0, 1880000000, 0.932, 2140, 2140],
  [new Date("2026-08-06"), 139930000, 11800000, 0, 1540000000, 0.917, 2080, 2080],
  [new Date("2026-08-07"), 80670000, 6330000, 0, 1050000000, 0.928, 1330, 1330],
  [new Date("2026-08-08"), 19420000, 2000000, 0, 475960000, 0.961, 748.34, 748.34],
  [new Date("2026-08-09"), 25840000, 2530000, 0, 564590000, 0.956, 698.79, 698.79],
  [new Date("2026-08-10"), 91070000, 7110000, 0, 1460000000, 0.941, 1460, 1460],
  [new Date("2026-08-11"), 111560000, 8650000, 0, 1620000000, 0.936, 1820, 1820],
  [new Date("2026-08-12"), 154400000, 7320000, 0, 967690000, 0.862, 1410, 1410],
  [new Date("2026-08-13"), 234920000, 8690000, 0, 834270000, 0.780, 1810, 1810],
];

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Token趋势");
sheet.showGridLines = false;

sheet.mergeCells("A1:I1");
sheet.getRange("A1").values = [["Token 使用趋势 / Token Usage Trend"]];
sheet.getRange("A1:I1").format.fill = "#0F172A";
sheet.getRange("A1:I1").format.font = { bold: true, color: "#FFFFFF", size: 16 };
sheet.getRange("A1:I1").format.rowHeight = 30;

sheet.mergeCells("A2:I2");
sheet.getRange("A2").values = [["统计范围 / Period: 2026-08-03 至 2026-08-13；来源 / Source: http://8.216.44.189:8080/admin/dashboard"]];
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
sheet.getRange("A5").values = [["口径说明 / Definition: Token 数值按后台图表提示中的 B/M 单位还原为绝对数量；Actual、Standard 为同一图表提示中的 USD 值。"]];
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

const dataMatrix = rows.map((row) => [row[0], row[1], row[2], row[3], row[4], row[5], null, row[6], row[7]]);
sheet.getRange("A8:I18").values = dataMatrix;
sheet.getRange("G8:G18").formulas = rows.map((_, index) => [`=SUM(B${index + 8}:E${index + 8})`]);

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

const table = sheet.tables.add("A7:I18", true, "TokenTrendTable");
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

const preview = await workbook.render({ sheetName: "Token趋势", range: "A1:L19", scale: 1.5, format: "png" });
await fs.writeFile(`${outputDir}/token_usage_preview.png`, new Uint8Array(await preview.arrayBuffer()));

const check = await workbook.inspect({
  kind: "table",
  range: "Token趋势!A1:I19",
  include: "values,formulas",
  tableMaxRows: 22,
  tableMaxCols: 10,
  tableMaxCellChars: 80,
});
console.log(check.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(`${outputDir}/token_usage_trend_2026-08-03_to_2026-08-13.xlsx`);
console.log(`SAVED ${outputDir}/token_usage_trend_2026-08-03_to_2026-08-13.xlsx`);
