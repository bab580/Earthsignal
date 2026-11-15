import unittest
from datetime import date, timedelta

from backend.app.analysis import analyze_rainfall_events, analyze_series


def daily_observations(start: date, end: date, value_for_date):
    rows = []
    current = start
    while current <= end:
        rows.append({
            "date": current.isoformat(),
            "PRECTOTCORR": value_for_date(current),
        })
        current += timedelta(days=1)
    return rows


class AnalysisTests(unittest.TestCase):
    def test_latest_month_compares_with_prior_same_calendar_month(self):
        start = date(2020, 1, 1)
        end = date(2024, 1, 31)
        observations = daily_observations(
            start,
            end,
            lambda day: 20 if day.year == 2024 else 10,
        )

        result = analyze_series(observations, "PRECTOTCORR", start, end)

        anomaly = result["latest_month_anomaly"]
        self.assertEqual(anomaly["status"], "unusual")
        self.assertEqual(anomaly["month"], 1)
        self.assertEqual(anomaly["baseline_years"], 4)
        self.assertEqual(anomaly["difference"], 10)

    def test_trend_uses_complete_years_and_reports_sen_slope(self):
        start = date(2018, 1, 1)
        end = date(2023, 12, 31)
        observations = daily_observations(
            start,
            end,
            lambda day: day.year - 2018,
        )

        result = analyze_series(observations, "PRECTOTCORR", start, end)

        self.assertEqual(result["trend"]["status"], "increasing")
        self.assertEqual(result["trend"]["sample_years"], 6)
        self.assertEqual(result["trend"]["sen_slope_per_year"], 1)
        self.assertLess(result["trend"]["p_value"], 0.05)

    def test_trend_is_not_claimed_with_too_few_complete_years(self):
        start = date(2022, 1, 1)
        end = date(2024, 12, 31)
        observations = daily_observations(start, end, lambda day: 1)

        result = analyze_series(observations, "PRECTOTCORR", start, end)

        self.assertEqual(result["trend"]["status"], "insufficient_history")
        self.assertEqual(result["trend"]["sample_years"], 3)

    def test_rainfall_screen_uses_wet_day_percentile(self):
        start = date(2025, 1, 1)
        end = start + timedelta(days=19)
        observations = daily_observations(start, end, lambda day: (day - start).days + 1)

        result = analyze_rainfall_events(observations, start, end)

        self.assertEqual(result["wet_day_count"], 20)
        self.assertAlmostEqual(result["threshold"], 19.05)
        self.assertEqual(result["high_rain_days"], [{"date": end.isoformat(), "rainfall": 20}])

    def test_rainfall_screen_needs_twenty_positive_wet_days(self):
        start = date(2025, 1, 1)
        end = start + timedelta(days=18)
        observations = daily_observations(start, end, lambda _: 2)

        result = analyze_rainfall_events(observations, start, end)

        self.assertIsNone(result["threshold"])
        self.assertEqual(result["high_rain_days"], [])

    def test_dry_spell_requires_fourteen_consecutive_valid_days(self):
        start = date(2025, 1, 1)
        end = start + timedelta(days=30)

        def rainfall(day):
            elapsed = (day - start).days
            if elapsed < 13:
                return 0
            if elapsed == 13:
                return 1
            if 14 <= elapsed < 28:
                return 0.5
            if elapsed == 28:
                return None
            return 0

        result = analyze_rainfall_events(daily_observations(start, end, rainfall), start, end)

        self.assertEqual(result["dry_spells"], [{
            "start": (start + timedelta(days=14)).isoformat(),
            "end": (start + timedelta(days=27)).isoformat(),
            "days": 14,
        }])


if __name__ == "__main__":
    unittest.main()
