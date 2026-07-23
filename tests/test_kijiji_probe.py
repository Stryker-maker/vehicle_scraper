import tempfile
import unittest
from pathlib import Path

from kijiji_probe import response_summary


class Response:
    status_code = 200
    url = "https://www.kijiji.ca/example"
    headers = {"Content-Type": "text/html", "Server": "test"}
    text = """
    <html><head><title>Search results</title></head><body>
      <script id="__NEXT_DATA__" type="application/json">{"props": {}}</script>
      <a href="/v-cars-trucks/edmonton/vehicle/123">Vehicle</a>
    </body></html>
    """


class KijijiProbeTests(unittest.TestCase):
    def test_response_summary_preserves_format_markers_without_secrets(self):
        summary = response_summary(Response(), "https://www.kijiji.ca/requested")
        self.assertEqual(summary["http_status"], 200)
        self.assertEqual(summary["page_title"], "Search results")
        self.assertIn("__next_data__", summary["data_markers"])
        self.assertEqual(summary["listing_link_count"], 1)
        self.assertEqual(summary["public_response_headers"]["content-type"], "text/html")
        self.assertNotIn("cookie", str(summary).casefold())
        self.assertNotIn("authorization", str(summary).casefold())


if __name__ == "__main__":
    unittest.main()
