# Stoch RSI Divergence v3 — Design Document

## Overview

A TradingView Pine Script v6 indicator that detects **regular divergences** between the Stochastic RSI `%K` oscillator and price. It uses a **K-first** approach: K pivots are the primary driver, and price is mapped to each K pivot after the fact.

The indicator draws divergence lines on both the Stoch RSI pane (K oscillator) and the price chart overlay, with optional debug markers.

---

## Core Algorithm

### 1. Detect K Pivots

On every bar, `ta.pivothigh(k, lbL, lbR)` and `ta.pivotlow(k, lbL, lbR)` are evaluated. When a pivot is confirmed, the actual pivot bar is `bar_index - lbR` (the confirmation delay).

### 2. Pair K Pivots: ks and ke

Consecutive K pivots of the same type are paired:
- `ks` = **start** (previous K pivot)
- `ke` = **end** (current K pivot, just confirmed)

### 3. K Divergence Shape Filter

Only keep the pair if the K oscillator forms the expected divergence shape:
- **Bearish divergence** (K highs): `keVal <= ksVal` — K makes a lower or equal high
- **Bullish divergence** (K lows): `keVal >= ksVal` — K makes a higher or equal low

### 4. Map K Pivots to Price

Each K pivot bar is mapped to the nearest **price pivot** within `+/- priceMapRadius` bars (default 5):
- For highs: find the nearest `is_price_pivot_high()` within the radius
- For lows: find the nearest `is_price_pivot_low()` within the radius
- **Fallback** (when `requireNearbyPricePivot = false`): if no price pivot found, use the bar with the max high (or min low) in the radius

### 5. Confirm Price Divergence

The divergence is confirmed only when price moves opposite to K:
- **Bearish**: `pePrice > psPrice` — price makes a higher high while K makes a lower high
- **Bullish**: `pePrice < psPrice` — price makes a lower low while K makes a higher low

---

## Two-Anchor Look-back System

### Problem Statement

Simple consecutive pairing misses important divergences when:
- **Case 6 (skip intermediate)**: An intermediate K pivot fails to map to price, breaking the chain from a valid `ks` to a valid `ke`
- **Case 7 (supersede smaller div)**: A confirmed divergence from `ks -> r` should be superseded by a larger `ks -> ke` when `ke` arrives later

### Solution: One-Step Anchor Memory

The indicator maintains **two** K anchors per side instead of one:

| Variable | Role |
|----------|------|
| `lastKHigh/LowBar/Val` | The most recent K pivot (current anchor, always advances) |
| `prevKHigh/LowBar/Val` | The K pivot before `lastK*` (one-step memory) |

### Flow When a New K Pivot `ke` Arrives

```
1. CONSECUTIVE test: lastKHigh -> ke
   Condition: keVal <= lastKHighVal (bear) or keVal >= lastKLowVal (bull)
   Map both to price, check price divergence -> consOk

2. LOOK-BACK test: prevKHigh -> ke  (independent of step 1)
   Condition: prevKHigh exists AND keVal <= prevKHighVal (bear) or keVal >= prevKLowVal (bull)
   Map both to price, check price divergence -> lbOk

3. Draw (look-back takes priority):
   If lbOk:
     - If active lines share the same ks -> dash them (supersede)
     - Draw prevK -> ke as solid. Store as new active.
   Else if consOk:
     - Draw lastK -> ke as solid. Store as new active.

4. Advance anchors:
   If direction break (ke exceeds last anchor):
     - Clear prevK, clear active lines
   Else if lbOk:
     - Do NOT advance prevK (keep original anchor pinned for chaining)
   Else:
     - prevK = lastK (shift one step back)
   lastK = ke (always)
```

### Anchor Pinning on Look-back (the critical fix)

When a look-back fires (`lbOk = true`), `prevK` is **not** advanced. This keeps the original anchor pinned so that if yet another K pivot arrives later, the look-back can chain again from the same origin, producing an even larger divergence and dashing the previous one.

Without this fix, `prevK` would shift to `lastK` on every iteration, losing the original `ks` reference after one step, causing visual clutter (multiple overlapping smaller divergences).

### Case 6 Trace (Skip Intermediate Failed Pivot)

```
T1: ks (K high 80) -> lastKHigh = ks
T2: i  (K high 75) ->
  Consecutive: ks -> i. FAILS (no price pivot near i).
  Look-back: prevKHigh is from before ks. Irrelevant.
  Advance: prevKHigh = ks, lastKHigh = i.
T3: ke (K high 70) ->
  Consecutive: i -> ke. May or may not confirm.
  Look-back: prevKHigh (ks, 80) -> ke (70). CONFIRMS!
  Draw ks -> ke solid. prevKHigh stays pinned (lbOk=true).
  Advance: lastKHigh = ke.
```

Result: `ks -> ke` drawn, intermediate `i` skipped.

### Case 7 Trace (Bigger Follow-up Supersedes)

```
T1: ks (K low 20) -> lastKLow = ks
T2: r  (K low 25) ->
  Consecutive: ks -> r. CONFIRMS! Draw ks -> r solid. Store active.
  Advance: prevKLow = ks, lastKLow = r.
T3: ke (K low 30) ->
  Consecutive: r -> ke. May or may not confirm.
  Look-back: prevKLow (ks, 20) -> ke (30). CONFIRMS!
  activeBullKsBar == prevKLowBar (both ks) -> DASH ks -> r lines.
  Draw ks -> ke solid. prevKLow stays pinned (lbOk=true).
  Advance: lastKLow = ke.
```

Result: `ks -> r` dashed, `ks -> ke` solid. Larger div supersedes.

---

## State Variables

### Bear Side (K Highs)

```pine
var int   lastKHighBar = na       // current anchor bar
var float lastKHighVal = na       // current anchor K value
var int   prevKHighBar = na       // one-step-back anchor bar
var float prevKHighVal = na       // one-step-back anchor K value
var line  activeBearKLine = na    // last confirmed div line on K pane
var line  activeBearPLine = na    // last confirmed div line on price overlay
var int   activeBearKsBar = na    // which ks bar the active lines reference
```

### Bull Side (K Lows)

```pine
var int   lastKLowBar = na
var float lastKLowVal = na
var int   prevKLowBar = na
var float prevKLowVal = na
var line  activeBullKLine = na
var line  activeBullPLine = na
var int   activeBullKsBar = na
```

---

## Pivot Helper Functions

Four functions check whether a given bar qualifies as a pivot by comparing it against `left` bars to the left and `right` bars to the right:

- `is_k_pivot_high(b, left, right)` — K value at bar `b` >= all neighbors
- `is_k_pivot_low(b, left, right)` — K value at bar `b` <= all neighbors
- `is_price_pivot_high(b, left, right)` — `high` at bar `b` >= all neighbors
- `is_price_pivot_low(b, left, right)` — `low` at bar `b` <= all neighbors

All include `>= 0` and `<= bar_index` bounds checks. In practice, this script constrains history access to 5,000 bars (`max_bars_back=5000` plus explicit `off <= 5000` checks in penetration loops).

## Price Mapping Functions

- `map_price_high_near(kBar, rad)` — returns `[price, bar]` of nearest price pivot high within `+/-rad` of `kBar`
- `map_price_low_near(kBar, rad)` — same for price pivot low

When `requireNearbyPricePivot = true` (default), these return `na` if no actual price pivot is found in the radius — preventing noise from fallback to local extremes.

When `requireNearbyPricePivot = false`, a fallback scans for the bar with the highest `high` (or lowest `low`) in the window and uses that as a pseudo-pivot.

---

## K-Line Penetration Filter

### Problem

Long-span divergence lines can cut through the K oscillator many times between `ks` and `ke`, producing visually noisy and low-conviction signals. However, a blanket "max crossings" threshold is too crude: a few bars crossing deeply is acceptable, and many bars crossing shallowly is also acceptable. Only when many bars cross deeply should the divergence be rejected.

### Solution: Average Penetration Depth

For each bar between `ks` and `ke`, interpolate the straight-line divergence value, then measure how far K penetrates through the wrong side:

```
For bar i (ksBar < i < keBar):
  lineVal = ksVal + slope * (i - ksBar)
  off = bar_index - (ksBar + i)
  Bear: penetration = max(0, k[off] - lineVal)   // K above line is bad
  Bull: penetration = max(0, lineVal - k[off])   // K below line is bad
```

The metric is:

```
avgPenetration = totalPenetration / span
```

If `avgPenetration > maxKPenetration`, the divergence is invalidated.

### Why This Works

| Scenario | Count | Depth | avgPenetration | Result |
|----------|-------|-------|----------------|--------|
| 3 bars cross by 1 pt over 20 bars | low | shallow | 0.15 | OK |
| 15 bars cross by 0.5 pt over 20 bars | high | shallow | 0.375 | OK |
| 15 bars cross by 5 pt over 20 bars | high | deep | 3.75 | REJECT |
| 2 bars cross by 8 pt over 20 bars | low | deep | 0.8 | OK |

The threshold is in K points (K ranges 0–100). A default of `2.0` means: on average across the span, K doesn't pierce the line by more than 2 points.

### Implementation

```pine
avg_k_penetration(int startBar, float startVal, int endBar, float endVal, bool checkAbove) =>
    int span = endBar - startBar
    if span <= 1
        0.0
    else
        float slope = (endVal - startVal) / span
        float total = 0.0
        for i = 1 to span - 1
            int off = bar_index - (startBar + i)
            if off >= 0 and off <= 5000
                float lineVal = startVal + slope * i
                float kVal = k[off]
                if checkAbove
                    total += math.max(0.0, kVal - lineVal)
                else
                    total += math.max(0.0, lineVal - kVal)
        total / span
```

The function is used as a final gate after K-shape + price-divergence checks.  
For Pine consistency, the script precomputes candidate penetration values at top level each bar, then applies them inside the confirmation branches:

```
avgPen = avg_k_penetration(ksBar, ksVal, keBar, keVal, true)  // true = bear
if avgPen > maxKPenetration
    consOk := false  // invalidate
```

### Price-Line Penetration (same principle)

The same average-penetration approach is applied to the price divergence line:

- **Bear** (price highs, line slopes up): penetration = `max(0, high[off] - lineVal)` — candles poking above the line
- **Bull** (price lows, line slopes down): penetration = `max(0, lineVal - low[off])` — candles dipping below the line

The raw price penetration is normalized by `atr14` to be instrument-agnostic:

```
if avgPricePenetration / atr14 > maxPricePenetration
    invalidate
```

When a look-back divergence fails price penetration, it falls through to the consecutive pair, which uses a closer `ps` and typically produces a cleaner line.

### Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| Max K penetration | float | 2.0 | Max average K-line penetration (K points) to allow divergence |
| Max price penetration | float | 0.3 | Max average price-line penetration (as ATR ratio) to allow divergence |

---

## Direction Break Reset

When a new K pivot breaks direction (e.g., a K high exceeds the previous K high), the entire look-back chain is invalidated:

```pine
if keVal > lastKHighVal        // bear side: direction break
    prevKHighBar := na         // clear look-back anchor
    prevKHighVal := na
    activeBearKLine := na      // clear active div tracking
    activeBearPLine := na
    activeBearKsBar := na
```

This prevents stale anchors from generating false divergences after trend reversals.

---

## Visual Output

### Lines

| What | Pane | Color | Width |
|------|------|-------|-------|
| Bearish K divergence | Stoch RSI | red | 2 |
| Bearish price divergence | Price overlay | `priceColorBear` (default: hot pink) | 2 |
| Bullish K divergence | Stoch RSI | green | 2 |
| Bullish price divergence | Price overlay | `priceColorBull` (default: yellow) | 2 |
| Superseded divergence | Either | dashed (same color) | 2 |

### Debug Markers (when `debugAllKPivots = true`)

| Marker | Location | Color | Size |
|--------|----------|-------|------|
| `▲` (K pivot high) | Stoch RSI pane (plotshape) | yellow | tiny |
| `▼` (K pivot low) | Stoch RSI pane (plotshape) | red | tiny |
| `▲` (price pivot high at ps/pe) | Price overlay (label) | blue | normal |
| `▼` (price pivot low at ps/pe) | Price overlay (label) | purple | normal |

Price low markers are offset downward by `max(syminfo.mintick * 12, atr14 * 0.15)` to avoid overlapping the candlestick.

---

## Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| K Smoothing | int | 3 | SMA smoothing for %K |
| D Smoothing | int | 3 | SMA smoothing for %D |
| RSI Length | int | 14 | RSI calculation period |
| Stochastic Length | int | 14 | Stochastic calculation period |
| RSI Source | source | close | Price source for RSI |
| Show Divergence Lines | bool | true | Master toggle for divergence detection |
| Pivot Right Lookback (lbR) | int | 2 | Bars to the right for pivot confirmation |
| Pivot Left Lookback (lbL) | int | 2 | Bars to the left for pivot confirmation |
| Bullish price line color | color | yellow | Color for bullish price divergence lines |
| Bearish price line color | color | hot pink | Color for bearish price divergence lines |
| Price map radius | int | 5 | +/- bars to search for price pivot near K pivot |
| Require nearby price pivot | bool | true | Disable fallback to local extreme when no pivot found |
| Max K penetration | float | 2.0 | Max average K-line penetration (K points) to allow divergence |
| Max price penetration | float | 0.3 | Max average price-line penetration (ATR ratio) to allow divergence |
| Debug: plot all K pivots | bool | true | Show all K pivot markers and price mapping labels |

---

## Design Iterations and Lessons Learned

### v1 — Original Consecutive Pairing
Simple `lastK -> ke` pairing. Worked for most cases but missed Case 6 (intermediate failures) and Case 7 (larger superseding divergences).

### Sticky Anchor (failed)
Changed anchor lifecycle so failed pivots didn't advance `lastK`. Caused anchor stagnation: one early failure froze the anchor, making all subsequent price mappings irrelevant. Result: no divergence lines at all.

### Superseded Div Logic (failed)
Attempted to manage line styling on top of sticky anchors. The underlying stagnation problem persisted.

### Two-Anchor Look-back (initial, partially worked)
Added `prevK` memory and tested both consecutive and look-back. Case 6 worked. Case 7 was messy because `prevK` advanced on every iteration, losing the original `ks` after one intermediate step. Multiple overlapping smaller divergences cluttered the chart.

### Two-Anchor with Anchor Pinning (current)
The fix: when look-back fires (`lbOk = true`), **do not advance `prevK`**. This keeps the original anchor pinned for chaining. Both Case 6 and Case 7 now work cleanly.

Key takeaway: the anchor lifecycle must **always advance `lastK`** (to avoid stagnation) but **selectively preserve `prevK`** (to maintain chain origin).

---

## File

- `indicators/stoch_rsi_divergence_v3.pine`
