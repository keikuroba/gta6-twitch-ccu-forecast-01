"""GTA VI Twitch CCU forecast: size-matched launch curves.

For every hour 2..24 of release day, forecast five quantiles of the
Twitch "Grand Theft Auto VI" category's concurrent viewers, anchored on
hour 1's print.

Method
------
A launch's audience curve depends strongly on how big its first hour
already is: a category that opens near-empty at 00:00 UTC (small
midnight audience) typically grows many-fold as the world wakes up and
unlocks roll across time zones, while a category that opens huge stays
roughly flat or decays. So instead of one pooled curve, this program
conditions on launch size: for the case at hand it takes the K
comparable past launches whose hour-1 viewer count is closest in log
space to this case's hour-1 print, and reads each hour's shape off
them -- the trimmed mean of their log-ratios log(viewers_h /
viewers_1), dropping the smallest and largest, as the centre, and the
standard deviation of those log-ratios as the spread. Trimming keeps
one unusual launch (a different unlock pattern, a data gap) from
dragging an hour's centre. Quantiles are then

    q_tau(h) = p1 * exp(centre_h + z_tau * spread_h)

with z the standard normal quantiles at the five scored levels. The
spread widens naturally through the day because launches disagree more
about later hours. When too few neighbours report an hour, the program
falls back to the same statistics over all usable comparables, and
then to a plain persistence forecast with a random-walk spread.

Only the case file is read. No network, no clock, no randomness: two
runs on the same input write byte-identical output.
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The scored quantile levels, in the order each output row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard normal quantiles at those levels.
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# How many size-nearest comparable launches shape each hour.
K_NEIGHBOURS = 12
# Narrowest spread allowed, in natural-log units (guards a degenerate
# neighbour set that happens to agree exactly).
SPREAD_FLOOR = 0.10
# Spread of the persistence fallback, log units per square-root hour.
BASELINE_SIGMA = 0.15
# A comparable only counts if its release day has hour 1 and at least
# this many hours of data.
MIN_CURVE_HOURS = 12


def _round2(x):
    """Round to 2 decimals, half up, returning an int for whole values."""
    scaled = x * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100.0
    return int(value) if value.is_integer() else value


def _when(text):
    """Parse an ISO timestamp ending in Z into an aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _release_day(comp):
    """A comparable's release-day curve as {hour 1..24: viewers}.

    The hour of a point is counted from the comparable's day_start
    (00:00 UTC of its release date). Points with no viewers are
    skipped; nothing is interpolated.
    """
    start = _when(comp["day_start"])
    curve = {}
    for point in comp.get("hourly") or []:
        viewers = point.get("viewers")
        if viewers is None or viewers <= 0:
            continue
        hour = int((_when(point["from"]) - start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            curve[hour] = viewers
    return curve


def _usable_curves(case):
    """Release-day curves of the case's comparables, usable ones only."""
    curves = []
    for comp in case.get("comparables") or []:
        curve = _release_day(comp)
        if 1 in curve and len(curve) >= MIN_CURVE_HOURS:
            curves.append(curve)
    return curves


def _mean_sd(values):
    """Mean and population standard deviation of a non-empty list."""
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, math.sqrt(var)


def _centre(ratios):
    """Trimmed mean of log-ratios: drop the extremes, average the rest.

    With three ratios this is the middle one; with more it averages the
    core, so one launch with a strange hour cannot move the centre.
    """
    ordered = sorted(ratios)
    core = ordered[1:-1] if len(ordered) > 2 else ordered
    return sum(core) / len(core)


def _hour_quantiles(p1, curves, hour):
    """Five quantiles for one hour from size-nearest comparables."""
    log_p1 = math.log(p1)
    ranked = sorted(
        curves,
        key=lambda c: (abs(math.log(c[1]) - log_p1), c[1]),
    )
    for pool in (ranked[:K_NEIGHBOURS], ranked):
        ratios = [math.log(c[hour] / c[1]) for c in pool if hour in c]
        if len(ratios) >= 3:
            centre = _centre(ratios)
            _, spread = _mean_sd(ratios)
            spread = max(spread, SPREAD_FLOOR)
            return [p1 * math.exp(centre + z * spread) for z in Z]
    # Too little comparable data for this hour: persistence fallback.
    return [p1 * math.exp(z * BASELINE_SIGMA * math.sqrt(hour - 1)) for z in Z]


def _hour_one_print(case):
    """Hour 1's viewer print; fall back to the last pre-release hour."""
    for row in case.get("known") or []:
        if row.get("hour") == 1 and row.get("viewers"):
            return max(1, row["viewers"])
    hourly = case.get("history_hourly") or []
    if hourly:
        last = hourly[-1].get("viewers")
        if last:
            return max(1, last)
    return 1


def forecast_case(case):
    """Forecast every hour the case asks for, as the output document."""
    p1 = _hour_one_print(case)
    curves = _usable_curves(case)
    rows = []
    for row in sorted(case["forecast"], key=lambda r: r["hour"]):
        hour = row["hour"]
        quantiles = _hour_quantiles(p1, curves, hour)
        fixed = []
        for q in quantiles:
            value = _round2(min(max(q, 0.01), 1e9))
            if fixed:
                value = max(value, fixed[-1])
            fixed.append(value)
        rows.append({"hour": hour, "q": fixed})
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        text = json.dumps(forecast, separators=(",", ":")) + "\n"
        (OUTPUT_DIR / f"{path.stem}.out").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
