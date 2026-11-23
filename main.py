"""cbBTC 1-minute trading bot for make.fun btc-race-24h-20261123-0511.

Strategy (long-only, $1,000 paper, no leverage, no shorts):
  * Buy early and stay invested: the dev window (22-23 Nov 2026, 1,440 bars)
    rises +3.64% with 1-minute noise of ~8 bps, while a full round trip costs
    ~26 bps (4 bps fee + 2 bps slippage each way + pool price impact). Any
    strategy that trades often loses to that friction: EMA(8/21) and
    EMA(12/26) crossovers lost -$120 on the dev window in local backtests,
    while buy-and-hold made +$32.
  * One position, full cash on entry, at bar 30 (30 bars of history first).
  * A 2% trailing stop from the peak close since entry caps the downside:
    on the dev window it never triggers (max drawdown -1.98%), so the bot
    keeps the full +$36.31 dev PnL; on a synthetic -8% crash it limits the
    loss to -$24 instead of buy-and-hold's -$81.
  * Re-entry only on a confirmed recovery, at least 60 bars after an exit:
    close above EMA(60) and above 98.5% of the peak it exited from.
    That re-enters a V-shaped recovery (local test: -$11 vs -$24 without
    re-entry) without re-entering a grinding downtrend.

Local backtests (own simulator, same fill model as the kit: fill at next
minute's open, 4 bps fee, 2 bps slippage, constant-product impact vs the
bar's open depth):
  dev window        +$36.31, 2 trades, max DD -1.98%
  reversed dev      -$35.76, 4 trades, max DD -4.28%  (buy-hold -$38.32)
  mirrored returns  -$28.88, 2 trades, max DD -2.89%  (buy-hold -$42.89)
  -8% crash, flat   -$24.42, 2 trades, max DD -2.44%  (buy-hold -$80.57)
  V-shape -3%/+3%   -$11.28, 4 trades, max DD -2.56%  (buy-hold  -$2.87)

Standard library only, deterministic: no network, no wall clock, no
randomness, no files. State is rebuilt from the bars the harness sends.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
ENTRY_BAR = 30          # first buy, once 30 bars of history exist
TRAIL_BPS = 200         # 2% trailing stop from peak close since entry
REENTRY_COOLDOWN = 60   # bars to wait after an exit before re-entering
REENTRY_PEAK_FRAC = 0.985  # re-enter only above 98.5% of the exit peak
EMA_SPAN = 60
MAX_SLIPPAGE_BPS = 500  # 5%: far above the largest 1-minute move in dev (0.72%)

closes = []             # close prices in dollars, in bar order
ema60 = None            # EMA(60) of closes
peak_since_entry = None
exit_peak = None
cooldown_until = -1


def _price(state):
    close_raw = state.close(SYMBOL)
    if close_raw is None:
        return None
    scale = state.hello["symbols"][0]["price_scale"]
    return close_raw / (10 ** scale)


def on_batch(state, batch):
    global ema60, peak_since_entry, exit_peak, cooldown_until
    price = _price(state)
    if price is None:
        return []
    closes.append(price)
    if ema60 is None:
        ema60 = price
    else:
        k = 2.0 / (EMA_SPAN + 1)
        ema60 += k * (price - ema60)

    if state.warming_up:
        return []

    holding = SYMBOL in state.positions
    seq = state.seq

    if holding:
        if peak_since_entry is None or price > peak_since_entry:
            peak_since_entry = price
        if price <= peak_since_entry * (1 - TRAIL_BPS / 10000.0):
            qty = state.positions[SYMBOL].qty
            exit_peak = peak_since_entry
            peak_since_entry = None
            cooldown_until = seq + REENTRY_COOLDOWN
            return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # Not holding.
    if seq < ENTRY_BAR:
        return []
    if exit_peak is None:
        # First entry (also retries it if the first buy was rejected).
        spend = min(state.cash, state.weight_room(SYMBOL))
    else:
        if seq <= cooldown_until:
            return []
        if exit_peak is None:
            return []
        if price <= ema60 or price <= exit_peak * REENTRY_PEAK_FRAC:
            return []
        spend = min(state.cash, state.weight_room(SYMBOL))
    if spend <= 0 or spend < int(state.hello["fees"]["min_notional_quote_units"]):
        return []
    peak_since_entry = price
    return [{"side": "buy", "symbol": SYMBOL, "notional_quote_units": spend,
             "max_slippage_bps": MAX_SLIPPAGE_BPS}]


makefun_bars.run(on_batch)
