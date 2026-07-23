import unittest

from kijiji_response_diagnostics import summarize_kijiji_html


class KijijiResponseDiagnosticsTests(unittest.TestCase):
    def test_sanitized_signature_exposes_response_shape(self):
        summary = summarize_kijiji_html(
            """<html><head><title>Results</title></head><body>
            <script type='application/ld+json'>{"@type":"ItemList","itemListElement":[]}</script>
            <script id='__NEXT_DATA__' type='application/json'>{}</script>
            <a href='/v-cars-trucks/edmonton/vehicle/123'>Vehicle</a>
            </body></html>"""
        )
        self.assertEqual(summary["page_title"], "Results")
        self.assertEqual(summary["json_ld_script_count"], 1)
        self.assertTrue(summary["next_data_present"])
        self.assertTrue(summary["item_list_marker_present"])
        self.assertEqual(summary["listing_link_count"], 1)
        self.assertNotIn("cookie", str(summary).casefold())
        self.assertNotIn("authorization", str(summary).casefold())


if __name__ == "__main__":
    unittest.main()
