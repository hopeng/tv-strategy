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
const { syncToTradingView } = require("./sync-pine-to-tv.cjs");

const ROOT = path.join(__dirname, "..");
const PINE_FILE = path.join(ROOT, "indicators", "stoch_rsi_divergence.pine");
const DEBOUNCE_MS = 10*1000;
let timer = null;

function push() {
  if (!fs.existsSync(PINE_FILE)) {
    console.error("Pine file not found:", PINE_FILE);
    process.exit(1);
  }
  console.log("\n---", new Date().toISOString(), "---");
  syncToTradingView({ pineFile: PINE_FILE });
  console.log("OK — synced to TradingView\n");
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
console.log("TV MCP:", process.env.TRADINGVIEW_MCP_ROOT || path.join(ROOT, "..", "tradingview-mcp-jackson"));
console.log("Debounced", DEBOUNCE_MS + "ms — leave this terminal open. Ctrl+C to stop.\n");

fs.watch(PINE_FILE, { persistent: true }, (eventType) => {
  if (eventType !== "change") return;
  schedulePush();
});
