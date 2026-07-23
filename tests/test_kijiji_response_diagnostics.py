import unittest

from kijiji_response_diagnostics import summarize_kijiji_html


class KijijiResponseDiagnosticsTests(unittest.TestCase):
    def test_sanitized_signature_exposes_response_shape(self):
        summary = summarize_kijiji_html(
            """<html><head><title>Results</title></head><body>
            <script type='application/ld+json'>{"@type":"ItemList","itemListElement":[]}</script>
            <script id='__NEXT_DATA__' type='application/json'>{"captcha":"bundled-library-name"}</script>
            <a href='/v-cars-trucks/edmonton/vehicle/123'>Vehicle</a>
            </body></html>"""
        )
        self.assertEqual(summary["page_title"], "Results")
        self.assertEqual(summary["json_ld_script_count"], 1)
        self.assertTrue(summary["next_data_present"])
        self.assertTrue(summary["item_list_marker_present"])
        self.assertEqual(summary["listing_link_count"], 1)
        self.assertEqual(summary["block_markers"], [])
        self.assertNotIn("cookie", str(summary).casefold())
        self.assertNotIn("authorization", str(summary).casefold())

    def test_visible_challenge_marker_is_reported(self):
        summary = summarize_kijiji_html(
            "<html><head><title>Verify you are human</title></head>"
            "<body>Please complete the CAPTCHA.</body></html>"
        )
        self.assertIn("verify you are human", summary["block_markers"])
        self.assertIn("captcha", summary["block_markers"])


if __name__ == "__main__":
    unittest.main()
