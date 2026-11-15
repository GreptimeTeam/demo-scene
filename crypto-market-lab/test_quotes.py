import unittest
from decimal import Decimal

from quotes import parse_quote


class QuotesTest(unittest.TestCase):
    def test_precision_and_crossed_quote(self):
        message = dict(s='BTCUSDT', u=42, b='100.00000001', B='2', a='100.00000002', A='3')
        quote = parse_quote(message, 1234567)
        self.assertEqual(quote[4] - quote[2], Decimal('0.00000001'))
        self.assertEqual(quote[-1], 1234567)
        with self.assertRaises(ValueError):
            parse_quote({**message, 'a': '99'}, 1234567)
        with self.assertRaises(ValueError):
            parse_quote({**message, 'b': '100.000000001'}, 1234567)



if __name__ == '__main__':
    unittest.main()
