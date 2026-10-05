import unittest
from unittest.mock import patch

from paper_evaluator.v2r4_precandidate_watcher import eur_pairs


class V2R4PreCandidateWatcherUniverseTests(unittest.TestCase):
    @patch("paper_evaluator.v2r4_precandidate_watcher.http_json")
    def test_eur_pairs_keeps_only_online_eur_markets(self, mock_http_json):
        mock_http_json.return_value = {
            "KSMEUR": {
                "wsname": "KSM/EUR",
                "altname": "KSMEUR",
                "quote": "ZEUR",
                "status": "online",
            },
            "TRACEUR": {
                "wsname": "TRAC/EUR",
                "altname": "TRACEUR",
                "quote": "ZEUR",
                "status": "online",
            },
            "OFFLINEEUR": {
                "wsname": "OFF/EUR",
                "altname": "OFFEUR",
                "quote": "ZEUR",
                "status": "cancel_only",
            },
            "BTCUSD": {
                "wsname": "XBT/USD",
                "altname": "XBTUSD",
                "quote": "ZUSD",
                "status": "online",
            },
        }

        pairs = eur_pairs()
        by_pair = {row["pair"]: row for row in pairs}

        self.assertEqual(set(by_pair), {"KSM/EUR", "TRAC/EUR"})
        self.assertEqual(by_pair["KSM/EUR"]["status"], "online")
        self.assertEqual(by_pair["TRAC/EUR"]["status"], "online")


if __name__ == "__main__":
    unittest.main()
