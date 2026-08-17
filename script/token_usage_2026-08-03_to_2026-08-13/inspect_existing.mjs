import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const path = "/Users/invictus/Github/ai-tools/outputs/2026-08-17-token-usage/token_usage_trend_2026-08-03_to_2026-08-13.xlsx";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(path));
const sheetInfo = await workbook.inspect({ kind: "sheet", include: "id,name" });
console.log(sheetInfo.ndjson);
const values = await workbook.inspect({
  kind: "table",
  range: "Token趋势!A1:L19",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 12,
  tableMaxCellChars: 80,
});
console.log(values.ndjson);
const preview = await workbook.render({ sheetName: "Token趋势", range: "A1:L19", scale: 1.5, format: "png" });
await fs.writeFile("/private/tmp/token_usage_existing_preview.png", new Uint8Array(await preview.arrayBuffer()));
console.log("RENDERED /private/tmp/token_usage_existing_preview.png");
