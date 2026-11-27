import os, unittest
from app import ai
class V04(unittest.TestCase):
    def test_no_key_fallback(self):
        os.environ.pop("GEMINI_API_KEY", None)
        r = ai.analyze("garbage", "garbage dump", "data:image/png;base64,AAAA")
        self.assertTrue(r["engine"].startswith("rules-v1"))
    def test_bad_key_falls_back(self):
        os.environ["GEMINI_API_KEY"] = "invalid"
        try: r = ai.analyze("garbage", "garbage dump near road", "data:image/png;base64,AAAA")
        finally: os.environ.pop("GEMINI_API_KEY")
        self.assertIn(r["category"], ai.CATS)
    def test_non_data_url_skips_vision(self):
        os.environ["GEMINI_API_KEY"] = "x"
        try: self.assertIsNone(ai._gemini("a", "b", "http://x/y.png", {}))
        finally: os.environ.pop("GEMINI_API_KEY")
if __name__ == "__main__": unittest.main()
