# cbBTC trading bot — btc-race-24h-20261123-0511

Long-only 1-minute cbBTC bot for make.fun. Buys early with full cash at bar 30,
holds through 1-minute noise, exits on a 2% trailing stop from the peak close
since entry, and re-enters only on a confirmed recovery (close above EMA(60)
and above 98.5% of the exit peak, after a 60-bar cooldown).

Local dev-window backtest (own simulator, kit fill model): **+$36.31 net PnL,
2 trades, max drawdown -1.98%** — passes the dev gate (net PnL > $0).
See `main.py` for the full backtest table, including crash / V-shape /
reversed-window stress tests.

Run: `python3 main.py` (Python 3.13, standard library only; `vendor/` holds a
copy of the kit's `makefun_bars.py` shim).
