import unittest
from datetime import date, datetime

from price_integrity import (
    extract_bigpara_quotes,
    parse_provider_date,
    same_price_series,
)


class PriceIntegrityTests(unittest.TestCase):
    def test_parse_provider_date_accepts_supported_formats(self):
        expected = date(2026, 7, 21)
        self.assertEqual(parse_provider_date('2026-07-21T18:10:00'), expected)
        self.assertEqual(parse_provider_date('21.07.2026 18:10'), expected)
        self.assertEqual(parse_provider_date('21/07/2026'), expected)
        self.assertEqual(
            parse_provider_date(datetime(2026, 7, 21, 18, 10)),
            expected,
        )

    def test_parse_provider_date_rejects_unknown_values(self):
        self.assertIsNone(parse_provider_date(None))
        self.assertIsNone(parse_provider_date(''))
        self.assertIsNone(parse_provider_date('21 Temmuz 2026'))

    def test_same_price_series_requires_equal_non_empty_sources(self):
        self.assertTrue(same_price_series('bigpara', 'bigpara'))
        self.assertTrue(same_price_series('yahoo_finance', 'yahoo_finance'))
        self.assertFalse(same_price_series('yahoo_finance', 'bigpara'))
        self.assertFalse(same_price_series(None, 'bigpara'))
        self.assertFalse(same_price_series('', ''))

    def test_bigpara_extractor_rejects_wrong_symbol_and_keeps_date(self):
        payload = {
            'data': {
                'unrelated': {
                    'sembol': 'OTHER',
                    'tarih': '2026-07-21T18:10:00',
                    'kapanis': '104,60',
                },
                'requested': {
                    'sembol': 'ALARK',
                    'tarih': '2026-07-21T18:10:00',
                    'kapanis': '109,60',
                },
            }
        }

        quotes = extract_bigpara_quotes(payload, 'ALARK')

        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0].price, 109.60)
        self.assertEqual(quotes[0].as_of_date, date(2026, 7, 21))


if __name__ == '__main__':
    unittest.main()
