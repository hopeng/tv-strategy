---
name: Update Anchor Logic To Cross-Only
overview: Update anchor selection so ks/ke no longer use %K pivot priority and instead always use K cross-down-through-D (bear) / cross-up-through-D (bull), while keeping the rest of the ps/pe state machine unchanged.
todos:
  - id: comment-update
    content: Update header comments to describe cross-only anchors
    status: completed
  - id: bear-anchor-refactor
    content: Refactor find_k_anchor_bear to cross-down-only selection
    status: completed
  - id: bull-anchor-refactor
    content: Refactor find_k_anchor_bull to cross-up-only selection
    status: completed
  - id: tv-verify
    content: Run pine check/set/compile and confirm no errors
    status: completed
isProject: false
---

# Update Anchor Logic To Cross-Only

Target file: [indicators/stoch_rsi_divergence.pine](d:/projects/tv-strategy/indicators/stoch_rsi_divergence.pine)

## Goal
Replace anchor selection behavior so divergence anchors are cross-only:
- Bear: ks/ke use K cross-down through D (closest to ps/pe within the window)
- Bull: ks/ke use K cross-up through D (closest to ps/pe within the window)
- Remove all %K pivot checks from anchor selection.

## Changes
- Update `find_k_anchor_bear(...)` to:
  - Remove the swing-high branch entirely.
  - Keep only the cross-down scan (`k[off] < d[off] and k[off + 1] >= d[off + 1]`).
  - Preserve distance-based closest bar selection and `excludeBar` behavior (`ke != ks`).
- Update `find_k_anchor_bull(...)` to:
  - Remove the swing-low branch entirely.
  - Keep only the cross-up scan (`k[off] > d[off] and k[off + 1] <= d[off + 1]`).
  - Preserve distance-based closest bar selection and `excludeBar` behavior.
- Update top comments to reflect cross-only anchor logic (remove mention of `%K swing high/low` priority).

## What stays unchanged
- ps/pe state machine and reset behavior.
- Window definition (`ps-5` to `pe+5`).
- Divergence comparison thresholds (`ke <= ks` for bear, `ke >= ks` for bull).
- Line drawing behavior and colors.

## Validation
- Run TradingView CLI check:
  - `pine check` for compile/lint.
  - `pine set` + `pine compile` to verify no runtime/compile errors in TradingView.
- Confirm zero errors and verify anchors still honor nearest-bar + `ke != ks` behavior.
