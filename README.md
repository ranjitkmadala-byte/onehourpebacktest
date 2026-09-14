# First 5-Minute Close-Below-Lower-Zone Backtest V3

This is the stricter rule requested.

Daily zone order:
SS -> WS -> WD -> SD

Qualification:
- Use the 09:15 OPEN to determine the starting higher zone.
- The completed 09:20 CLOSE must be BELOW the LOW boundary of the lower zone.
- A mere intrabar touch/low through the lower zone does NOT qualify.
- The deepest lower zone fully broken by the 09:20 close becomes the end zone.

Examples:
- SS -> WS: qualify only if 09:20 close < Weak Supply Low
- WS -> WD: qualify only if 09:20 close < Weak Demand Low
- WD -> SD: qualify only if 09:20 close < Strong Demand Low
- SS -> WD: qualify if close is below Weak Demand Low
- WS -> SD: qualify if close is below Strong Demand Low

Trade:
- Entry = LOW of the completed 09:15-09:20 candle
- Target = HIGH boundary of the next zone below the end zone
- Stop = LOW boundary of the previous zone above the end zone
- Evaluate outcome after 09:20
- Same 1-minute target/stop = AMBIGUOUS
- Neither = EOD

Tables:
- public.first5_close_below_lower_zone_backtest
- public.first5_close_below_lower_zone_summary
