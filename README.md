# Weak Demand 5m Break -> Anytime AVWAP Retrace -> ATM PE -> Strong Demand Target

This is the revised version with the 10:15 / 10:45 timing logic removed.

Zone source
-----------
Both Weak Demand and Strong Demand are mirrored from the supplied Pine daily-zone formulas.

Weak Demand:
- dist_weak = sigma / (2 * sqrt(2))
- ww = round(sigma / (4 * phi))
- weak_demand_low  = round(P - dist_weak - ww/2)
- weak_demand_high = round(P - dist_weak + ww/2)

Strong Demand:
- dist_strong = sigma
- ws = round(sigma / 4)
- strong_demand_low  = round(P - sigma - ws/2)
- strong_demand_high = round(P - sigma + ws/2)

Revised backtest rule
---------------------
1. The completed 09:15-09:20 SPOT 5-minute candle must CLOSE below Weak Demand Low.
2. From 09:20 onward, price may retrace to AVWAP at ANY TIME.
3. Retrace = a completed 3-minute candle high touches/crosses AVWAP.
4. Bearish spot setup = first LATER completed 3-minute candle closes below AVWAP.
5. Setup must occur by ENTRY_CUTOFF (default 12:15, configurable).
6. Select nearest-expiry ATM CE + PE.
7. Bearish option score:
   - PE premium up
   - PE OI down
   - CE premium down
   - CE OI up
8. Require score EXACTLY 3 within 15 minutes after the AVWAP spot entry.
9. No 10:45-11:15 option time filter.
10. Require ATM PE entry premium >= Rs 10.
11. TARGET = Daily Strong Demand HIGH boundary (first boundary reached from above).
12. STOP = +0.5% from the AVWAP spot entry.
13. Exit 100% ATM PE when Strong Demand target or stop occurs first; neither -> EOD.

Default study window: 2026-08-26 through 2026-09-11.

Writes:
- public.weak_demand_5m_avwap_pe_backtest
- public.weak_demand_5m_avwap_pe_summary
