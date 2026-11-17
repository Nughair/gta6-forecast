# gta6-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Nughair/gta6-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Nughair/gta6-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

A forecaster for Grand Theft Auto VI's launch-day Twitch viewers: for each of hours 2–24 of 2026-11-19 (UTC) it writes the 5/25/50/75/95% quantiles of that hour's mean concurrent viewers in the "Grand Theft Auto VI" category, scored by pinball loss on the log scale. The model is fitted at run time on the case's own comparables — forty-plus past big launches with hourly category counts. Each comparable contributes its release-day ratio curve (hourly prints over its hour-1 print, in log space, winsorised at ±2); per hour the curves are summarised by a weighted median and a robust spread, with kernel weights that favour launches resembling this case — close in hour-1 size (Gaussian kernel on log size), close in pre-release ramp (the biggest of the 12 pre-day hours over hour 1), and console-only, as GTA VI is a console launch. The five quantiles come from the standardised residuals of the fitted curves, pooled within three blocks of hours (the morning dip, the afternoon, the evening rise), so the tails borrow strength from hundreds of residuals rather than a few dozen points per hour. Leave-one-out over the comparable launches, run through this exact program, scores a mean pinball loss of 0.253 against the house persistence baseline's 0.321 on the launches whose first hour drew at least 20,000 viewers (0.259 against 0.360 above 5,000). If a case's comparables cannot be used, the program falls back to the persistence shape so a case is never invalid; it is deterministic and runs in well under a second.

## Run it

```sh
python3 main.py
# reads every *.in in $MAKEFUN_INPUT_DIR (or /input), writes <id>.out to $MAKEFUN_OUTPUT_DIR (or /output)
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=lucky-comet-18&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
