#!/usr/bin/env node
/**
 * Cursor afterFileEdit hook: after the agent edits a .pine file, push to TradingView (same CLI as npm run push:tv).
 * Stdin: JSON with file_path (see Cursor hooks docs). Exits 0 quietly if not a .pine file.
 */
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

function main() {
  let input = "";
  try {
    input = fs.readFileSync(0, "utf8");
  } catch {
    process.exit(0);
  }
  if (!input.trim()) process.exit(0);

  let data;
  try {
    data = JSON.parse(input);
  } catch {
    process.exit(0);
  }

  const fp = data.file_path || data.filePath || "";
  if (!fp.toLowerCase().endsWith(".pine")) process.exit(0);

  const abs = path.resolve(fp.replace(/\//g, path.sep));
  if (!fs.existsSync(abs)) process.exit(0);

  const projectRoot = path.join(__dirname, "..", "..");
  const TV_MCP_ROOT =
    process.env.TRADINGVIEW_MCP_ROOT ||
    path.join(projectRoot, "..", "tradingview-mcp-jackson");
  const CLI = path.join(TV_MCP_ROOT, "src", "cli", "index.js");
  if (!fs.existsSync(CLI)) {
    console.error("[push-pine-after-edit] Missing CLI:", CLI);
    process.exit(0);
  }

  const run = (args) => {
    execFileSync(process.execPath, [CLI, ...args], {
      stdio: "inherit",
      cwd: TV_MCP_ROOT,
    });
  };

  console.error("[push-pine-after-edit]", abs);
  run(["pine", "set", "-f", abs]);
  run(["pine", "compile"]);
  run(["pine", "save"]);
}

main();
