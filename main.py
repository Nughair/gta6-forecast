"""gta6-twitch-ccu-forecast-01: forecast GTA VI's launch-day Twitch viewers, hours 2..24.

The model is fitted at run time on the case's own comparables (past big launches with
hourly Twitch category counts). For every comparable launch we take its release-day
ratio curve r_h = print_h / print_1 in log space. A launch's curve is then summarised
per hour by a weighted median and a robust spread, where the weights favour launches
whose hour-1 size and pre-release ramp resemble this case's:

  weight = gauss(log p1 distance, bw 1.0)
         * gauss(log premax distance, bw 0.7)   (premax = biggest pre-day hour / p1)
         * 1.6 if the comparable is console-only (GTA VI is a console launch)

Quantiles come from the standardised residuals of the fitted curves, pooled within
three blocks of hours (2-8, 9-16, 17-24), so the 5% and 95% levels borrow strength
from hundreds of residuals instead of ~40 noisy points each while still letting the
tail shape differ between the morning dip and the evening rise. Log ratios are
winsorised at +/-2 before fitting, so one freak launch (a single global unlock hour
that makes its ratios explode) cannot bend a neighbourhood it barely belongs to.
Everything is a deterministic function of the case file; if the comparables cannot be
used, the forecast falls back to the house persistence shape (flat at hour 1, spread
widening like sqrt(h - 1)) so a case is never left invalid.

Run contract (the grader's): python3 /bot/main.py reads every *.in in the input dir
($MAKEFUN_INPUT_DIR or /input) and writes <id>.out per case to the output dir
($MAKEFUN_OUTPUT_DIR or /output): {"hours": [{"hour": h, "q": [5 quantiles]}]}.
Standard library only, no network.
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z_NORM = [-1.645, -0.674, 0.0, 0.674, 1.645]

BW_LOGP1 = 1.0        # kernel width on log hour-1 size
BW_PREMAX = 0.7       # kernel width on log pre-release peak ratio
CONSOLE_BOOST = 1.6   # extra weight for console-only comparables
MIN_P1 = 1000         # a comparable needs a real first hour to carry a ratio curve
SIGMA_FLOOR = 0.08    # never claim a tighter hour than this, in log units
WINSOR = 2.0          # clip log ratios to +/- this before fitting
BLOCKS = ((2, 8), (9, 16), (17, 24))  # residual pools: dip, afternoon, evening rise


def parse_ts(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def hour_offsets(day_start, hourly):
    """Map whole-hour offsets from day_start to a point's viewers."""
    start = parse_ts(day_start)
    pts = {}
    for point in hourly or []:
        try:
            off = (parse_ts(point["from"]) - start).total_seconds() / 3600.0
            viewers = point["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        if viewers is not None and off == int(off):
            pts[int(off)] = float(viewers)
    return pts


def premax_ratio(pts, p1):
    """Largest of the 12 hourly prints before the day, over hour 1's print (log)."""
    pre = [pts[k] for k in range(-12, 0) if k in pts and pts[k] > 0]
    if not pre or p1 <= 0:
        return None
    return math.log(max(pre) / p1)


def launch_curve(comp, game_name):
    """One comparable's release day as log ratios to its own hour 1, or None."""
    if comp.get("name", "").startswith(game_name):
        return None  # the case game's own category history is not a launch
    pts = hour_offsets(comp["day_start"], comp.get("hourly"))
    day = [pts.get(h - 1) for h in range(1, 25)]
    if not day[0] or day[0] < MIN_P1:
        return None
    p1 = day[0]
    ratios = {}
    for h in range(2, 25):
        if day[h - 1]:
            ratios[h] = math.log(day[h - 1] / p1)
    if len(ratios) < 12:
        return None
    return {
        "logp1": math.log(p1),
        "lpremax": premax_ratio(pts, p1),
        "console_only": "PC" not in (comp.get("platforms") or ""),
        "ratios": ratios,
    }


def wquantile(pairs, t):
    """Interpolated weighted quantile of (value, weight) pairs."""
    ordered = sorted(pairs)
    total = sum(w for _, w in ordered)
    if total <= 0:
        return ordered[len(ordered) // 2][0]
    acc = 0.0
    cum = []
    for value, w in ordered:
        acc += w
        cum.append((value, acc / total))
    for i, (value, c) in enumerate(cum):
        if c >= t:
            if i == 0:
                return value
            prev_v, prev_c = cum[i - 1]
            if c == prev_c:
                return value
            return prev_v + (t - prev_c) / (c - prev_c) * (value - prev_v)
    return ordered[-1][0]


def weight_of(launch, logp1, lpremax):
    w = math.exp(-0.5 * ((launch["logp1"] - logp1) / BW_LOGP1) ** 2)
    if lpremax is not None and launch["lpremax"] is not None:
        w *= math.exp(-0.5 * ((launch["lpremax"] - lpremax) / BW_PREMAX) ** 2)
    if launch["console_only"]:
        w *= CONSOLE_BOOST
    return w


def model_forecast(case, p1, levels):
    """Fit on the case's comparables; return {hour: [quantiles]} or None."""
    game_name = (case.get("game") or {}).get("name", "")
    launches = []
    for comp in case.get("comparables") or []:
        try:
            curve = launch_curve(comp, game_name)
        except (KeyError, TypeError, ValueError):
            curve = None
        if curve is not None:
            launches.append(curve)
    if len(launches) < 8:
        return None

    logp1 = math.log(p1)
    own_pts = {}
    for row in case.get("history_hourly") or []:
        try:
            own_pts[row["from"]] = row["viewers"]
        except (KeyError, TypeError):
            continue
    start = parse_ts(case["day_start"])
    pre_pts = {}
    for text, viewers in own_pts.items():
        off = (parse_ts(text) - start).total_seconds() / 3600.0
        if off == int(off) and viewers:
            pre_pts[int(off)] = float(viewers)
    lpremax = premax_ratio(pre_pts, p1)

    weights = [weight_of(L, logp1, lpremax) for L in launches]
    mus, sigs = {}, {}
    block_res = {b: [] for b in range(len(BLOCKS))}
    for h in range(2, 25):
        pairs = [
            (max(-WINSOR, min(WINSOR, L["ratios"][h])), w)
            for L, w in zip(launches, weights)
            if h in L["ratios"]
        ]
        if len(pairs) < 8:
            return None
        mu = wquantile(pairs, 0.5)
        sigma = max(SIGMA_FLOOR, (wquantile(pairs, 0.75) - wquantile(pairs, 0.25)) / 1.349)
        mus[h], sigs[h] = mu, sigma
        block = next(i for i, (lo, hi) in enumerate(BLOCKS) if lo <= h <= hi)
        block_res[block].extend(((v - mu) / sigma, w) for v, w in pairs)
    block_zq = {
        b: {t: wquantile(res, t) for t in levels} for b, res in block_res.items()
    }
    out = {}
    for h in range(2, 25):
        block = next(i for i, (lo, hi) in enumerate(BLOCKS) if lo <= h <= hi)
        row = []
        for t in levels:
            q = p1 * math.exp(mus[h] + sigs[h] * block_zq[block][t])
            row.append(min(1e9, max(0.01, q)))
        for i in range(1, len(row)):
            row[i] = max(row[i], row[i - 1])
        out[h] = row
    return out


def fallback_forecast(p1, hours, levels):
    """The house persistence shape: flat at hour 1, spread ~ sqrt(h - 1)."""
    out = {}
    for h in hours:
        row = []
        for t in levels:
            z = Z_NORM[LEVELS.index(t)] if t in LEVELS else 0.0
            row.append(min(1e9, max(0.01, p1 * math.exp(z * 0.15 * math.sqrt(h - 1)))))
        out[h] = row
    return out


def round2(x):
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if float(value).is_integer() else value


def forecast_case(case):
    levels = case.get("levels") or LEVELS
    first = next((k for k in case.get("known") or [] if k.get("hour") == 1), None)
    if first is None:
        raise ValueError("case has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    hours = [row["hour"] for row in case.get("forecast") or []]
    if not hours:
        hours = list(range(2, 25))
    try:
        pred = model_forecast(case, p1, levels)
    except Exception:
        pred = None
    if pred is None:
        pred = fallback_forecast(p1, hours, levels)
    rows = [{"hour": h, "q": [round2(v) for v in pred[h]]} for h in hours]
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
