#!/usr/bin/env node
/**
 * Watch indicators/stoch_rsi_divergence.pine and push to TradingView via tradingview-mcp-jackson CLI.
 *
 * Usage:
 *   node scripts/watch-pine-to-tv.cjs
 *   node scripts/watch-pine-to-tv.cjs --once
 *
 * Set TRADINGVIEW_MCP_ROOT if the MCP repo is not next to this repo (default: ../tradingview-mcp-jackson).
 */

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = path.join(__dirname, "..");
const PINE_FILE = path.join(ROOT, "indicators", "stoch_rsi_divergence.pine");
const TV_MCP_ROOT =
  process.env.TRADINGVIEW_MCP_ROOT ||
  path.join(ROOT, "..", "tradingview-mcp-jackson");
const CLI = path.join(TV_MCP_ROOT, "src", "cli", "index.js");

const DEBOUNCE_MS = 600;
let timer = null;

function push() {
  if (!fs.existsSync(CLI)) {
    console.error("TV MCP CLI not found:", CLI);
    console.error("Clone or set TRADINGVIEW_MCP_ROOT to your tradingview-mcp-jackson path.");
    process.exit(1);
  }
  if (!fs.existsSync(PINE_FILE)) {
    console.error("Pine file not found:", PINE_FILE);
    process.exit(1);
  }
  const run = (args) => {
    execFileSync(process.execPath, [CLI, ...args], {
      stdio: "inherit",
      cwd: TV_MCP_ROOT,
    });
  };
  console.log("\n---", new Date().toISOString(), "---");
  run(["pine", "set", "-f", PINE_FILE]);
  run(["pine", "compile"]);
  run(["pine", "save"]);
  console.log("OK — pushed & saved to TradingView\n");
}

function schedulePush() {
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    timer = null;
    try {
      push();
    } catch (e) {
      console.error(e.message || e);
    }
  }, DEBOUNCE_MS);
}

const once = process.argv.includes("--once");
if (!fs.existsSync(PINE_FILE)) {
  console.error("Missing:", PINE_FILE);
  process.exit(1);
}

if (once) {
  push();
  process.exit(0);
}

console.log("Watching:", PINE_FILE);
console.log("TV MCP:", TV_MCP_ROOT);
console.log("Debounced", DEBOUNCE_MS + "ms — leave this terminal open. Ctrl+C to stop.\n");

fs.watch(PINE_FILE, { persistent: true }, (eventType) => {
  if (eventType !== "change") return;
  schedulePush();
});
