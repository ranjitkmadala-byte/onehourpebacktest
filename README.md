# First 5-Minute One-or-More Zone Traversal Backtest

Daily zone order:
Strong Supply (SS) -> Weak Supply (WS) -> Weak Demand (WD) -> Strong Demand (SD)

Qualification:
The 09:15-09:20 SPOT candle must fall downward by AT LEAST ONE zone step.

Now qualifying examples:
- SS -> WS
- WS -> WD
- WD -> SD
- SS -> WD
- WS -> SD
- SS -> SD

Entry:
- LOW of the completed 09:15-09:20 candle.

Target:
- HIGH boundary of the next zone below the entry/end-zone.

Stop:
- LOW boundary of the previous zone above the entry/end-zone.

No AVWAP.
No options.
No fixed-percentage target/stop.

Output tables:
- public.first5_one_or_more_zone_traversal_backtest
- public.first5_one_or_more_zone_traversal_summary
