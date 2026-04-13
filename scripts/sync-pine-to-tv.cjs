#!/usr/bin/env node
/**
 * Sync Pine source to TradingView, compile, check errors,
 * and ensure the indicator is on chart.
 *
 * Usage:
 *   node scripts/sync-pine-to-tv.cjs
 *
 * Env overrides:
 *   TRADINGVIEW_MCP_ROOT  - path to tradingview-mcp-jackson repo
 *   PINE_FILE             - path to .pine file (default indicators/stoch_rsi_divergence.pine)
 *   TV_SCRIPT_NAME        - TradingView saved script name (default "Stoch RSI Div")
 */

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = path.join(__dirname, "..");

function fail(msg, err) {
  console.error(msg);
  if (err) console.error(err.message || err);
  process.exit(1);
}

function runJson(cliPath, tvMcpRoot, args, label) {
  try {
    const out = execFileSync(process.execPath, [cliPath, ...args], {
      cwd: tvMcpRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
    if (!out) return {};
    try {
      return JSON.parse(out);
    } catch {
      // Some commands may print extra lines; try last JSON object line.
      const lines = out.split(/\r?\n/).filter(Boolean);
      const last = lines[lines.length - 1];
      return JSON.parse(last);
    }
  } catch (err) {
    fail(`Command failed: ${label} (${args.join(" ")})`, err);
  }
}

function getIndicatorTitle(pineSource) {
  const m = pineSource.match(/indicator\(\s*title\s*=\s*"([^"]+)"/);
  return m ? m[1] : null;
}

function hasStudy(state, title) {
  if (!state || !Array.isArray(state.studies)) return false;
  return state.studies.some((s) => {
    const n = (s && s.name) || "";
    if (n === title) return true;
    // Fallback for older title/name mismatch (e.g. v2 naming drift)
    return title && n.includes("Stoch RSI Divergence");
  });
}

function syncToTradingView(options = {}) {
  const tvMcpRoot =
    options.tvMcpRoot ||
    process.env.TRADINGVIEW_MCP_ROOT ||
    path.join(ROOT, "..", "tradingview-mcp-jackson");
  const cliPath = path.join(tvMcpRoot, "src", "cli", "index.js");
  const pineFile =
    options.pineFile ||
    process.env.PINE_FILE ||
    path.join(ROOT, "indicators", "stoch_rsi_divergence.pine");
  const tvScriptName = options.tvScriptName || process.env.TV_SCRIPT_NAME || "Stoch RSI Div";

  if (!fs.existsSync(cliPath)) {
    fail(
      `TradingView MCP CLI not found: ${cliPath}\nSet TRADINGVIEW_MCP_ROOT or clone tradingview-mcp-jackson beside this repo.`
    );
  }
  if (!fs.existsSync(pineFile)) {
    fail(`Pine file not found: ${pineFile}`);
  }

  const pineSource = fs.readFileSync(pineFile, "utf8");
  const indicatorTitle = getIndicatorTitle(pineSource);

  console.log("TV MCP:", tvMcpRoot);
  console.log("Pine file:", pineFile);
  if (indicatorTitle) console.log("Indicator title:", indicatorTitle);
  console.log("Saved script name:", tvScriptName);

  // Open saved script in Pine editor if available.
  const openRes = runJson(cliPath, tvMcpRoot, ["pine", "open", "--name", tvScriptName], "pine open");
  if (!openRes.success) {
    console.warn(`Warning: could not open saved script "${tvScriptName}". Continuing.`);
  }

  const setRes = runJson(cliPath, tvMcpRoot, ["pine", "set", "-f", pineFile], "pine set");
  if (!setRes.success) fail("pine set failed.");

  const compileRes = runJson(cliPath, tvMcpRoot, ["pine", "compile"], "pine compile");
  if (!compileRes.success) fail("pine compile failed.");

  const errorsRes = runJson(cliPath, tvMcpRoot, ["pine", "errors"], "pine errors");
  if (!errorsRes.success) fail("pine errors failed.");
  if (errorsRes.error_count > 0 || errorsRes.has_errors) {
    console.error("Compilation errors detected:");
    console.error(JSON.stringify(errorsRes.errors || [], null, 2));
    process.exit(2);
  }

  // Ensure script is on chart. If absent, trigger Add/Update via Ctrl+Enter.
  let state = runJson(cliPath, tvMcpRoot, ["state"], "state");
  let added = hasStudy(state, indicatorTitle);
  if (!added) {
    console.log("Indicator not on chart. Sending Ctrl+Enter...");
    runJson(cliPath, tvMcpRoot, ["ui", "keyboard", "Enter", "--ctrl"], "ui keyboard ctrl+enter");
    // Re-check state and errors after hotkey.
    state = runJson(cliPath, tvMcpRoot, ["state"], "state");
    const postErr = runJson(cliPath, tvMcpRoot, ["pine", "errors"], "pine errors after ctrl+enter");
    if (postErr.error_count > 0 || postErr.has_errors) {
      console.error("Errors after Ctrl+Enter:");
      console.error(JSON.stringify(postErr.errors || [], null, 2));
      process.exit(3);
    }
    added = hasStudy(state, indicatorTitle);
  }

  console.log("\nSync complete.");
  console.log(`Compile errors: ${errorsRes.error_count || 0}`);
  console.log(`Indicator on chart: ${added ? "yes" : "no"}`);
  if (!added) {
    console.warn(
      "Indicator was not detected on chart automatically. Check active TradingView tab/layout and try again."
    );
  }

  return { added, errors: errorsRes.error_count || 0 };
}

module.exports = { syncToTradingView };

if (require.main === module) {
  syncToTradingView();
}

