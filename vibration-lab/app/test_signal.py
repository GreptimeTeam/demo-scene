import unittest

import numpy as np

from main import SAMPLE_RATE, features, signal_window


class SignalTest(unittest.TestCase):
    def test_fft_amplitude_and_frequency(self):
        signal = 0.75 * np.sin(2 * np.pi * 30 * np.arange(SAMPLE_RATE) / SAMPLE_RATE)
        rms, _, _, spectrum = features(signal)
        self.assertEqual(int(np.argmax(spectrum)), 30)
        self.assertAlmostEqual(spectrum[30], 0.75, places=4)
        self.assertAlmostEqual(rms, 0.75 / np.sqrt(2), places=6)
        self.assertEqual(len(spectrum), 513)

    def test_injected_faults_have_distinct_features(self):
        normal = features(signal_window('normal', np.random.default_rng(42)))
        imbalance = features(signal_window('imbalance', np.random.default_rng(42)))
        looseness = features(signal_window('looseness', np.random.default_rng(42)))
        self.assertGreater(imbalance[0], normal[0] * 4)
        self.assertGreater(looseness[2], imbalance[2] * 2)
        self.assertGreater(looseness[3][60], normal[3][60] * 20)
        self.assertGreater(looseness[3][90], normal[3][90] * 20)


if __name__ == '__main__':
    unittest.main()
