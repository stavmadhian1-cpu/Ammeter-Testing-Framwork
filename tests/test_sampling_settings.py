import unittest

from src.testing.results import SamplingSettings


class SamplingSettingsTest(unittest.TestCase):
    """
    The three sampling values are linked (count = duration * frequency): any two give the third.
    """

    def test_third_value_is_calculated(self):
        self.assertEqual(SamplingSettings.from_values(duration=5, frequency=20).count, 100)
        self.assertEqual(SamplingSettings.from_values(count=100, frequency=20).duration, 5)
        self.assertEqual(SamplingSettings.from_values(count=100, duration=5).frequency, 20)

    def test_interval_is_one_over_frequency(self):
        self.assertAlmostEqual(SamplingSettings.from_values(count=10, frequency=20).interval, 0.05)

    def test_all_three_values_must_match(self):
        self.assertEqual(SamplingSettings.from_values(count=100, duration=5, frequency=20).count, 100)
        with self.assertRaisesRegex(ValueError, "don't match"):
            SamplingSettings.from_values(count=99, duration=5, frequency=20)

    def test_invalid_values_are_rejected(self):
        invalid = [
            {"count": 10},                        # Only one value
            {"count": 0, "frequency": 10},        # Zero
            {"duration": -1, "frequency": 10},    # Negative
            {"duration": 0.01, "frequency": 10},  # Less than 1 measurement
            {"count": 10.5, "frequency": 10},     # Not a whole number
        ]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                SamplingSettings.from_values(**values)


if __name__ == "__main__":
    unittest.main()
