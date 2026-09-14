# Weak Demand 09:20 Low Entry — 0.5% Target / Day-High Stop

Signal:
- Completed 09:15-09:20 SPOT candle CLOSES below Daily Weak Demand Low.

Entry:
- Short at LOW of the completed 09:15-09:20 candle.

Target:
- 0.5% below entry.

Stop:
- Day/session high known at the moment of entry.
- At 09:20, that is the HIGH of the completed 09:15-09:20 opening candle.
- The backtest does NOT use the eventual full-day high because that would introduce future leakage.

Outcome:
- Evaluate only after the 09:20 signal candle is complete.
- Target first / stop first.
- Same 1-minute target+stop occurrence = AMBIGUOUS_SAME_1M_BAR.
- Neither = EOD.

Output:
- public.weak_demand_5m_0920_low_day_high_backtest
- public.weak_demand_5m_0920_low_day_high_summary
