import unittest

from backend.app.appeears import _matches_task_request, _parse_sample_csv


class AppEEARSTests(unittest.TestCase):
    def test_converts_scaled_modis_values_and_excludes_bad_quality_samples(self):
        csv_text = (
            "Date,MOD13Q1.061:_250m_16_days_NDVI,MOD13Q1.061:_250m_16_days_VI_Quality,"
            "MOD11A2.061:LST_Day_1km,MOD11A2.061:QC_Day\n"
            "2024-01-01,0.75,0,300,0\n"
            "2024-01-09,0.9,1,310,1\n"
            "2024-01-17,0.6,4,310,0\n"
        )

        observations = _parse_sample_csv(csv_text)

        self.assertEqual(observations["2024-01-01"]["NDVI"], 0.75)
        self.assertEqual(observations["2024-01-01"]["LST_DAY_C"], 26.85)
        self.assertIsNone(observations["2024-01-09"]["NDVI"])
        self.assertIsNone(observations["2024-01-09"]["LST_DAY_C"])
        self.assertEqual(observations["2024-01-17"]["NDVI"], 0.6)
        self.assertEqual(observations["2024-01-17"]["LST_DAY_C"], 36.85)

    def test_requires_result_date_and_layer_columns(self):
        with self.assertRaisesRegex(ValueError, "Date column"):
            _parse_sample_csv("Latitude,Longitude\n2.2,32.8\n")

    def test_existing_task_must_match_requested_location_and_period(self):
        request = {
            "task_name": "EarthSignal point analysis",
            "task_type": "point",
            "params": {
                "dates": [{"startDate": "01-01-2025", "endDate": "01-31-2025"}],
                "layers": [{"product": "MOD13Q1.061", "layer": "_250m_16_days_NDVI"}],
                "coordinates": [{"latitude": 2.2499, "longitude": 32.8998}],
            },
        }
        task = {
            "task_name": "EarthSignal point analysis",
            "task_type": "point",
            "params": {
                **request["params"],
                "coordinates": [{"latitude": 2.2499, "longitude": 32.8998}],
            },
        }

        self.assertTrue(_matches_task_request(task, request))
        task["params"]["coordinates"][0]["longitude"] = 32.3
        self.assertFalse(_matches_task_request(task, request))


if __name__ == "__main__":
    unittest.main()
