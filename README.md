# Strong Demand breakdown -> AVWAP -> ATM PE backtest

Mirror of the Strong Supply bullish study.

Rules:
1. SPOT 09:15-10:15 completed 1-hour candle closes below Strong Demand Low.
2. AVWAP accumulates from 09:15. The 09:15 3-minute HIGH is stored as the bearish anchor context.
3. After 10:15, wait for a 3-minute bar HIGH to touch/cross AVWAP.
4. Entry setup occurs on the first LATER completed 3-minute candle closing BELOW AVWAP, no later than 12:15.
5. Select nearest-expiry ATM CE + PE at the spot entry.
6. Bearish option confirmation score:
   - PE premium up = 1
   - PE OI down = 1
   - CE premium down = 1
   - CE OI up = 1
7. Exact option entry = ATM PE when score first reaches >=3 within 15 minutes.
8. Spot target = -0.5% from the original AVWAP spot entry.
9. Spot stop = +0.5% from the original AVWAP spot entry.
10. Exit 100% of ATM PE at whichever spot level occurs first; if neither, EOD.

The target/stop outcome scan begins only after the ATM PE option-entry confirmation, so the result is executable without look-ahead.

Writes:
- public.spot_demand_1015_avwap_pe_backtest
- public.spot_demand_1015_avwap_pe_summary

Uses the same historical study window by default: 2026-08-26 through 2026-09-11.
Universe is taken from distinct symbols already present in public.spot_supply_1h_backtest_hourly.
