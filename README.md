# sandbox

Local scripts and tools.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

```bash
uv run python <script.py>
```

## Dependencies

- `mcp` — MCP protocol library
- `yt-dlp` — YouTube/media downloader



# Simplified Stoch RSI Div logic:
## Bear Div (bull div is opposite):
1. price chart: save if there's a pivot as ps. When there's a next pivot, if it's higher than ps, then save it as pe. if it's lower than ps, then replace ps with the new pivot
2. check stoch rsi within the range between ps and pe and widen it by extra 5 bars on each end.
3. find k line starting point ks correspond to ps: it's a pivot, or the crossing point closest to ps when k crossing down 
4. find k line end point ke correspond to pe: it's a pivot, or the crossing point closest to pe when k crossing down, and ke can't be the same as ks. 
5. if ke is lower than ks, divergence is confirmed! draw line between ps-pe and ks-ke
6. note: pivot for both price and k uses 5 bar left lookback and 3 bar right lookback

