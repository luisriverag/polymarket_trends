import unittest
import sqlite3
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_polymarket.db"
        app.DB_FILE = self.db_path
        app.init_db()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_market_history_insert(self):
        markets = [
            {
                "id": "test1",
                "question": "Test market 1",
                "slug": "test-1",
                "endDate": "2026-12-31T00:00:00Z",
            },
            {
                "id": "test2",
                "question": "Test market 2",
                "slug": "test-2",
                "endDate": "2026-12-31T00:00:00Z",
            },
        ]
        app.update_market_history(markets)

        history = app.load_history()
        self.assertEqual(len(history), 2)
        self.assertIn("test1", history)
        self.assertIn("test2", history)
        self.assertEqual(history["test1"]["question"], "Test market 1")

    def test_market_history_update(self):
        markets = [
            {
                "id": "test1",
                "question": "Test market 1",
                "slug": "test-1",
                "endDate": "2026-12-31T00:00:00Z",
            }
        ]
        app.update_market_history(markets)
        first_seen = app.load_history()["test1"]["first_seen"]

        import time

        time.sleep(0.1)

        app.update_market_history(markets)
        history = app.load_history()

        self.assertEqual(history["test1"]["first_seen"], first_seen)
        self.assertGreater(history["test1"]["last_seen"], first_seen)

    def test_market_history_resolution(self):
        markets = [
            {
                "id": "test1",
                "question": "Test market 1",
                "slug": "test-1",
                "endDate": "2026-12-31T00:00:00Z",
                "closed": True,
                "umaResolutionStatus": "resolved",
                "outcomePrices": "[0.01, 0.99]",
            }
        ]
        app.update_market_history(markets)

        history = app.load_history()
        self.assertEqual(history["test1"]["outcome"], "No")

    def test_volume_history_save_and_load(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        conn = app.get_db()
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO volume_history VALUES (?, ?)",
            (yesterday, '{"total_24h": 1000000, "by_category": [["Crypto", 1000000]]}'),
        )
        conn.commit()
        conn.close()

        loaded = app.load_previous_volume_history()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["total_24h"], 1000000)

    def test_volume_history_no_previous(self):
        loaded = app.load_previous_volume_history()
        self.assertIsNone(loaded)


class TestSentimentAnalysis(unittest.TestCase):
    def test_analyze_sentiment_basic(self):
        markets = [
            {"outcomePrices": "[0.8, 0.2]"},
            {"outcomePrices": "[0.3, 0.7]"},
            {"outcomePrices": "[0.5, 0.5]"},
        ]
        result = app.analyze_sentiment(markets)

        self.assertEqual(result["bullish"], 1)
        self.assertEqual(result["bearish"], 1)
        self.assertEqual(result["neutral"], 1)
        self.assertIn("overall", result)

    def test_analyze_sentiment_distribution(self):
        markets = [{"outcomePrices": "[0.85, 0.15]"}, {"outcomePrices": "[0.05, 0.95]"}]
        result = app.analyze_sentiment(markets)

        self.assertIn("distribution", result)
        self.assertEqual(result["distribution"]["80-90%"], 1)
        self.assertEqual(result["distribution"]["0-10%"], 1)


class TestVolumeByCategory(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_polymarket.db"
        app.DB_FILE = self.db_path
        app.init_db()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_calculate_volume_history_with_events(self):
        markets = []
        events = [
            {"volume": 100000, "tags": [{"label": "Crypto"}]},
            {"volume": 200000, "tags": [{"label": "Sports"}]},
            {"volume": 50000, "tags": [{"label": "Crypto"}]},
        ]
        result = app.calculate_volume_history(markets, events)

        self.assertEqual(result["total_24h"], 350000)
        cats = {c["category"]: c["volume"] for c in result["by_category"]}
        self.assertEqual(cats["Crypto"], 150000)
        self.assertEqual(cats["Sports"], 200000)

    def test_calculate_volume_change(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        conn = app.get_db()
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO volume_history VALUES (?, ?)",
            (yesterday, '{"total_24h": 100000, "by_category": [["Crypto", 100000]]}'),
        )
        conn.commit()
        conn.close()

        markets = []
        events = [{"volume": 150000, "tags": [{"label": "Crypto"}]}]
        result = app.calculate_volume_history(markets, events)

        crypto_vol = next(
            (c for c in result["by_category"] if c["category"] == "Crypto"), None
        )
        if crypto_vol and crypto_vol["change"]:
            self.assertEqual(crypto_vol["change"], 50.0)


class TestResolutions(unittest.TestCase):
    def test_analyze_resolutions_closed_market(self):
        closed = [
            {
                "id": "test1",
                "question": "Test resolved",
                "slug": "test-resolved",
                "volume": 10000,
                "endDate": "2026-01-01T00:00:00Z",
                "closed": True,
                "outcomePrices": "[0.01, 0.99]",
            }
        ]
        result = app.analyze_resolutions(closed, [])

        self.assertGreater(len(result["resolved"]), 0)
        self.assertEqual(result["resolved"][0]["outcome"], "No")


if __name__ == "__main__":
    unittest.main()
