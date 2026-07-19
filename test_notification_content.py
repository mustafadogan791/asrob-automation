import unittest

from notification_content import (
    POLL_OPENED_BODY,
    POLL_OPENED_TITLE,
    RESULTS_READY_TITLE,
    VOTING_CLOSING_BODY,
    VOTING_CLOSING_TITLE,
)


class NotificationContentTests(unittest.TestCase):
    def test_poll_opened_copy(self):
        self.assertEqual(POLL_OPENED_TITLE, "Yeni Oylamalar Aktif")
        self.assertEqual(
            POLL_OPENED_BODY,
            "Piyasanın yönünü analiz et. Topluluk ne diyor?",
        )

    def test_voting_closing_copy(self):
        self.assertEqual(VOTING_CLOSING_TITLE, "Oylar Kapanmak Üzere")
        self.assertEqual(
            VOTING_CLOSING_BODY,
            "Son tahminlerini yap; oylar 09.30'da kapanıyor.",
        )

    def test_results_ready_copy(self):
        self.assertEqual(RESULTS_READY_TITLE, "Puan ve Sıralamanı Gör!")


if __name__ == "__main__":
    unittest.main()
