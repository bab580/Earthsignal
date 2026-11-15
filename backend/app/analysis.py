from collections import defaultdict
from datetime import date, timedelta
import math
from statistics import median
from typing import Any


MINIMUM_TREND_YEARS = 5
MINIMUM_BASELINE_YEARS = 3
MINIMUM_COVERAGE = 0.8
ROBUST_ANOMALY_THRESHOLD = 3.5


def _valid_values(observations: list[dict[str, Any]], parameter: str) -> list[tuple[date, float]]:
    values = []
    for row in observations:
        raw_date = row.get("date")
        raw_value = row.get(parameter)
        if raw_value is None:
            continue
        try:
            observed_date = date.fromisoformat(raw_date)
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append((observed_date, value))
    return sorted(values)


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1) - timedelta(days=1)
    return date(year, month + 1, 1) - timedelta(days=1)


def _complete_months(
    values: list[tuple[date, float]], start: date, end: date, cadence_days: int
) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int], list[float]] = defaultdict(list)
    for observed_date, value in values:
        grouped[(observed_date.year, observed_date.month)].append(value)

    months = []
    for (year, month), readings in sorted(grouped.items()):
        month_start = date(year, month, 1)
        month_end = _month_end(year, month)
        expected_days = (month_end - month_start).days + 1
        expected_observations = max(1, math.ceil(expected_days / cadence_days))
        coverage_threshold = MINIMUM_COVERAGE if cadence_days == 1 else 0.5
        if month_start < start or month_end > end or len(readings) / expected_observations < coverage_threshold:
            continue
        months.append({
            "year": year,
            "month": month,
            "mean": sum(readings) / len(readings),
            "valid_observations": len(readings),
            "expected_observations": expected_observations,
        })
    return months


def _latest_month_anomaly(months: list[dict[str, Any]]) -> dict[str, Any]:
    if not months:
        return {"status": "insufficient_history", "reason": "No complete months have enough valid observations."}

    latest = months[-1]
    baseline = [
        item["mean"] for item in months
        if item["month"] == latest["month"] and item["year"] < latest["year"]
    ]
    if len(baseline) < MINIMUM_BASELINE_YEARS:
        return {
            "status": "insufficient_history",
            "year": latest["year"],
            "month": latest["month"],
            "baseline_years": len(baseline),
            "required_baseline_years": MINIMUM_BASELINE_YEARS,
        }

    baseline_median = median(baseline)
    mad = median([abs(value - baseline_median) for value in baseline])
    difference = latest["mean"] - baseline_median
    score = difference / (1.4826 * mad) if mad > 0 else None
    is_anomaly = abs(score) >= ROBUST_ANOMALY_THRESHOLD if score is not None else difference != 0
    return {
        "status": "unusual" if is_anomaly else "within_baseline_range",
        "year": latest["year"],
        "month": latest["month"],
        "observed": round(latest["mean"], 4),
        "baseline_median": round(baseline_median, 4),
        "difference": round(difference, 4),
        "robust_score": round(score, 3) if score is not None else None,
        "baseline_years": len(baseline),
        "baseline_method": "Median and median absolute deviation of earlier complete observations for the same calendar month.",
        "threshold": ROBUST_ANOMALY_THRESHOLD,
    }


def _complete_years(
    values: list[tuple[date, float]], start: date, end: date, cadence_days: int
) -> list[dict[str, Any]]:
    grouped: dict[int, list[float]] = defaultdict(list)
    for observed_date, value in values:
        grouped[observed_date.year].append(value)

    years = []
    for year, readings in sorted(grouped.items()):
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        expected_days = (year_end - year_start).days + 1
        expected_observations = math.ceil(expected_days / cadence_days)
        coverage_threshold = MINIMUM_COVERAGE if cadence_days == 1 else 0.7
        if year_start < start or year_end > end or len(readings) / expected_observations < coverage_threshold:
            continue
        years.append({
            "year": year,
            "mean": sum(readings) / len(readings),
            "valid_observations": len(readings),
            "expected_observations": expected_observations,
        })
    return years


def _mann_kendall(years: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = []
    s = 0
    for left_index, left in enumerate(years):
        for right in years[left_index + 1:]:
            delta = right["mean"] - left["mean"]
            s += (delta > 0) - (delta < 0)
            pairs.append(delta / (right["year"] - left["year"]))

    counts: dict[float, int] = defaultdict(int)
    for point in years:
        counts[point["mean"]] += 1
    n = len(years)
    tie_adjustment = sum(count * (count - 1) * (2 * count + 5) for count in counts.values())
    variance = (n * (n - 1) * (2 * n + 5) - tie_adjustment) / 18
    if variance <= 0 or s == 0:
        z_score = 0.0
        p_value = 1.0
    else:
        z_score = (s - 1) / math.sqrt(variance) if s > 0 else (s + 1) / math.sqrt(variance)
        p_value = math.erfc(abs(z_score) / math.sqrt(2))

    slope = median(pairs) if pairs else 0.0
    significant = p_value < 0.05
    direction = "increasing" if significant and slope > 0 else "decreasing" if significant and slope < 0 else "no_significant_trend_detected"
    return {
        "status": direction,
        "method": "Mann-Kendall test on complete calendar-year means with Sen's slope.",
        "sample_years": n,
        "first_year": years[0]["year"],
        "last_year": years[-1]["year"],
        "sen_slope_per_year": round(slope, 6),
        "p_value": round(p_value, 6),
        "significance_level": 0.05,
        "annual_means": [
            {"year": item["year"], "mean": round(item["mean"], 4), "valid_observations": item["valid_observations"]}
            for item in years
        ],
    }


def analyze_series(
    observations: list[dict[str, Any]], parameter: str, start: date, end: date, cadence_days: int = 1
) -> dict[str, Any]:
    values = _valid_values(observations, parameter)
    if cadence_days < 1:
        raise ValueError("cadence_days must be a positive number.")
    monthly_coverage = MINIMUM_COVERAGE if cadence_days == 1 else 0.5
    annual_coverage = MINIMUM_COVERAGE if cadence_days == 1 else 0.7
    months = _complete_months(values, start, end, cadence_days)
    years = _complete_years(values, start, end, cadence_days)
    trend = (
        _mann_kendall(years)
        if len(years) >= MINIMUM_TREND_YEARS
        else {
            "status": "insufficient_history",
            "method": "Mann-Kendall test on complete calendar-year means with Sen's slope.",
            "sample_years": len(years),
            "required_years": MINIMUM_TREND_YEARS,
            "annual_means": [
                {"year": item["year"], "mean": round(item["mean"], 4), "valid_observations": item["valid_observations"]}
                for item in years
            ],
        }
    )
    return {
        "coverage": {
            "valid_observations": len(values),
            "complete_months": len(months),
            "complete_years": len(years),
            "expected_cadence_days": cadence_days,
            "minimum_monthly_coverage": monthly_coverage,
            "minimum_annual_coverage": annual_coverage,
        },
        "latest_month_anomaly": _latest_month_anomaly(months),
        "trend": trend,
        "interpretation_note": (
            "Historical anomaly and trend comparisons are descriptive, not forecasts or evidence of causation. "
            "Annual and monthly aggregates are calculated by EarthSignal; incomplete calendar periods are excluded."
        ),
    }


def analyze_observations(
    observations: list[dict[str, Any]], start: date, end: date
) -> dict[str, Any]:
    return {
        parameter: analyze_series(observations, parameter, start, end)
        for parameter in ("PRECTOTCORR", "T2M")
    }


def analyze_rainfall_events(
    observations: list[dict[str, Any]], start: date, end: date
) -> dict[str, Any]:
    rainfall_by_date = {
        observed_date: value
        for observed_date, value in _valid_values(observations, "PRECTOTCORR")
        if start <= observed_date <= end and value >= 0
    }
    wet_day_amounts = sorted(value for value in rainfall_by_date.values() if value > 0)
    threshold = None
    high_rain_days = []
    if len(wet_day_amounts) >= 20:
        index = (len(wet_day_amounts) - 1) * 0.95
        lower = math.floor(index)
        fraction = index - lower
        threshold = wet_day_amounts[lower] + (
            wet_day_amounts[min(lower + 1, len(wet_day_amounts) - 1)] - wet_day_amounts[lower]
        ) * fraction
        high_rain_days = [
            {"date": observed_date.isoformat(), "rainfall": round(value, 3)}
            for observed_date, value in sorted(rainfall_by_date.items())
            if value > 0 and value >= threshold
        ]

    dry_spells = []
    spell_start = None
    spell_days = 0

    def finish_spell() -> None:
        nonlocal spell_start, spell_days
        if spell_start is not None and spell_days >= 14:
            spell_end = spell_start + timedelta(days=spell_days - 1)
            dry_spells.append({
                "start": spell_start.isoformat(),
                "end": spell_end.isoformat(),
                "days": spell_days,
            })
        spell_start = None
        spell_days = 0

    observed_date = start
    while observed_date <= end:
        value = rainfall_by_date.get(observed_date)
        if value is not None and value < 1:
            if spell_start is None:
                spell_start = observed_date
            spell_days += 1
        else:
            finish_spell()
        observed_date += timedelta(days=1)
    finish_spell()

    return {
        "threshold": round(threshold, 3) if threshold is not None else None,
        "wet_day_count": len(wet_day_amounts),
        "high_rain_days": high_rain_days,
        "dry_spells": dry_spells,
    }
