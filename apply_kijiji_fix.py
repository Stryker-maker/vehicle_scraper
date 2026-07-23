from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one match in {path}: found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


adapter = ROOT / "kijiji_adapter.py"
replace_once(
    adapter,
    "from kijiji_locations import LOCATION_REGISTRY_VERSION, validate_query_locations\n",
    "from kijiji_locations import LOCATION_REGISTRY_VERSION, validate_query_locations\n"
    "from kijiji_response_diagnostics import summarize_kijiji_html\n",
)
replace_once(
    adapter,
    '''def _fuel_and_engine(text: str) -> tuple[str, str]:
    lowered = text.casefold()
    if "hybrid" in lowered:
        fuel = "Hybrid"
    elif "electric" in lowered:
        fuel = "Electric"
    elif "diesel" in lowered:
        fuel = "Diesel"
    elif re.search(r"\\b(?:gas|gasoline|petrol)\\b", lowered):
        fuel = "Gas"
    else:
        fuel = "Unknown"
    match = re.search(r"\\b(\\d+(?:\\.\\d+)?)\\s*[lL]\\b", text)
    return fuel, f"{match.group(1)}L" if match else "Unknown"
''',
    '''def _structured_engine_parts(item: dict[str, Any]) -> list[str]:
    value = item.get("vehicleEngine")
    values = value if isinstance(value, list) else [value]
    parts: list[str] = []
    for entry in values:
        if isinstance(entry, dict):
            for key in (
                "fuelType",
                "name",
                "description",
                "engineDisplacement",
                "engineType",
                "configuration",
            ):
                field = entry.get(key)
                if isinstance(field, dict):
                    field = field.get("value") or field.get("name")
                if field not in (None, ""):
                    parts.append(str(field).strip())
        elif entry not in (None, ""):
            parts.append(str(entry).strip())
    return [part for part in parts if part]


def _fuel_and_engine(item: dict[str, Any], text: str) -> tuple[str, str]:
    structured_parts = _structured_engine_parts(item)
    combined = " ".join([text, *structured_parts]).strip()
    lowered = combined.casefold()
    structured_fuel = " ".join(
        part for part in structured_parts if part.casefold() in {
            "gas", "gasoline", "petrol", "diesel", "hybrid", "electric"
        }
    ).casefold()
    fuel_text = structured_fuel or lowered
    if "hybrid" in fuel_text:
        fuel = "Hybrid"
    elif "electric" in fuel_text:
        fuel = "Electric"
    elif "diesel" in fuel_text:
        fuel = "Diesel"
    elif re.search(r"\\b(?:gas|gasoline|petrol|unleaded)\\b", fuel_text):
        fuel = "Gas"
    else:
        fuel = "Unknown"
    match = re.search(
        r"\\b(\\d+(?:\\.\\d+)?)\\s*(?:l|litre|liter)\\b",
        combined,
        flags=re.IGNORECASE,
    )
    return fuel, f"{match.group(1)}L" if match else "Unknown"
''',
)
replace_once(
    adapter,
    "    fuel, engine = _fuel_and_engine(combined)\n",
    "    fuel, engine = _fuel_and_engine(item, combined)\n",
)
replace_once(
    adapter,
    '                items, json_errors = extract_page_payload(response.text)\n'
    '                request_record["json_ld_errors"] = json_errors\n',
    '                items, json_errors = extract_page_payload(response.text)\n'
    '                request_record["json_ld_errors"] = json_errors\n'
    '                request_record["response_diagnostics"] = summarize_kijiji_html(\n'
    '                    response.text\n'
    '                )\n',
)

workflow = ROOT / ".github" / "workflows" / "scrape.yml"
replace_once(
    workflow,
    "      - name: Prepare single-pair validation artifact\n"
    "        if: env.COLLECTION_SCOPE == 'single_pair'\n",
    "      - name: Prepare single-pair validation artifact\n"
    "        if: always() && env.COLLECTION_SCOPE == 'single_pair'\n",
)
replace_once(
    workflow,
    "      - name: Upload single-pair validation artifact\n"
    "        if: env.COLLECTION_SCOPE == 'single_pair'\n",
    "      - name: Upload single-pair validation artifact\n"
    "        if: always() && env.COLLECTION_SCOPE == 'single_pair'\n",
)
replace_once(
    workflow,
    '''        run: |
          set -euo pipefail
          artifact="$RUNNER_TEMP/smoke-artifact"
          mkdir -p "$artifact/run_status" "$artifact/latest" "$artifact/evidence"
          cp "data/$VEHICLE_KEY/run_status/${SELECTED_SOURCE}_latest.json" "$artifact/run_status/"
          cp "data/$VEHICLE_KEY/latest/${VEHICLE_KEY}_${SELECTED_SOURCE}_latest.csv" "$artifact/latest/"
          cp -R "data/$VEHICLE_KEY/evidence/$SELECTED_SOURCE/." "$artifact/evidence/"
          if [[ -d "data/$VEHICLE_KEY/adapter_evidence/$SELECTED_SOURCE" ]]; then
            mkdir -p "$artifact/adapter_evidence"
            cp -R "data/$VEHICLE_KEY/adapter_evidence/$SELECTED_SOURCE/." "$artifact/adapter_evidence/"
          fi
          mkdir -p "$artifact/identity_lifecycle"
          cp -R "data/$VEHICLE_KEY/identity_lifecycle/$SELECTED_SOURCE/." "$artifact/identity_lifecycle/"
          if [[ -d "data/$VEHICLE_KEY/buyer_intelligence" ]]; then
            mkdir -p "$artifact/buyer_intelligence"
            cp -R "data/$VEHICLE_KEY/buyer_intelligence/." "$artifact/buyer_intelligence/"
          fi
          if [[ -d "data/$VEHICLE_KEY/purpose_output" ]]; then
            mkdir -p "$artifact/purpose_output"
            cp -R "data/$VEHICLE_KEY/purpose_output/." "$artifact/purpose_output/"
          fi
          cp "${{ steps.collection-plan.outputs.path }}" "$artifact/source-plan.tsv"
''',
    '''        run: |
          set -euo pipefail
          artifact="$RUNNER_TEMP/smoke-artifact"
          rm -rf "$artifact"
          mkdir -p "$artifact"
          copy_file() {
            local source="$1" destination="$2"
            if [[ -f "$source" ]]; then
              mkdir -p "$destination"
              cp "$source" "$destination/"
            fi
          }
          copy_dir() {
            local source="$1" destination="$2"
            if [[ -d "$source" ]]; then
              mkdir -p "$destination"
              cp -R "$source/." "$destination/"
            fi
          }
          copy_file "data/$VEHICLE_KEY/run_status/${SELECTED_SOURCE}_latest.json" "$artifact/run_status"
          copy_file "data/$VEHICLE_KEY/latest/${VEHICLE_KEY}_${SELECTED_SOURCE}_latest.csv" "$artifact/latest"
          copy_dir "data/$VEHICLE_KEY/evidence/$SELECTED_SOURCE" "$artifact/evidence"
          copy_dir "data/$VEHICLE_KEY/adapter_evidence/$SELECTED_SOURCE" "$artifact/adapter_evidence"
          copy_dir "data/$VEHICLE_KEY/identity_lifecycle/$SELECTED_SOURCE" "$artifact/identity_lifecycle"
          copy_dir "data/$VEHICLE_KEY/buyer_intelligence" "$artifact/buyer_intelligence"
          copy_dir "data/$VEHICLE_KEY/purpose_output" "$artifact/purpose_output"
          cp "${{ steps.collection-plan.outputs.path }}" "$artifact/source-plan.tsv"
          find "$artifact" -type f -maxdepth 8 -print | sort
''',
)

(ROOT / "kijiji_response_diagnostics.py").write_text(
    '''from __future__ import annotations

import hashlib
from typing import Any

from bs4 import BeautifulSoup

BLOCK_MARKERS = (
    "access denied",
    "captcha",
    "cloudflare",
    "datadome",
    "incapsula",
    "perimeterx",
    "px-captcha",
    "robot check",
    "verify you are human",
)


def summarize_kijiji_html(html: str) -> dict[str, Any]:
    text = str(html or "")
    encoded = text.encode("utf-8", errors="replace")
    lowered = text.casefold()
    soup = BeautifulSoup(text, "html.parser")
    scripts = soup.find_all("script")
    listing_links = {
        str(anchor.get("href"))
        for anchor in soup.find_all("a", href=True)
        if "/v-cars-trucks/" in str(anchor.get("href"))
    }
    return {
        "response_bytes": len(encoded),
        "response_sha256": hashlib.sha256(encoded).hexdigest(),
        "page_title": soup.title.get_text(" ", strip=True) if soup.title else None,
        "script_count": len(scripts),
        "script_types": sorted({str(script.get("type") or "") for script in scripts}),
        "json_ld_script_count": sum(
            str(script.get("type") or "").casefold() == "application/ld+json"
            for script in scripts
        ),
        "next_data_present": soup.find("script", id="__NEXT_DATA__") is not None,
        "item_list_marker_present": "itemlistelement" in lowered,
        "listing_link_count": len(listing_links),
        "block_markers": [marker for marker in BLOCK_MARKERS if marker in lowered],
        "text_sample": " ".join(soup.stripped_strings)[:1000],
    }
''',
    encoding="utf-8",
)

(ROOT / "tests" / "test_kijiji_structured_fields.py").write_text(
    '''import unittest

from kijiji_adapter import parse_listing


class KijijiStructuredFieldTests(unittest.TestCase):
    def config(self, *, fuel="Gas", engine=""):
        return {
            "criteria": {
                "min_year": 2018,
                "max_year": 2023,
                "max_price_cad": 60000,
                "fuel": fuel,
                "engine": engine,
            },
            "sources": {"kijiji": {"make": "Honda", "model": "Odyssey"}},
        }

    def item(self, *, fuel_type="gas", engine_name=None):
        vehicle_engine = {"@type": "EngineSpecification", "fuelType": fuel_type}
        if engine_name:
            vehicle_engine["name"] = engine_name
        return {
            "@type": "Car",
            "name": "2019 Honda Odyssey EX-L",
            "description": "Well maintained family van",
            "url": "https://www.kijiji.ca/v-cars-trucks/edmonton/vehicle/1234567890",
            "vehicleModelDate": "2019",
            "mileageFromOdometer": {"value": "120000"},
            "offers": {"price": "32995"},
            "vehicleEngine": vehicle_engine,
        }

    def test_structured_gas_field_prevents_false_fuel_unknown(self):
        row, rejections, failures = parse_listing(
            self.item(),
            config=self.config(),
            tiers={"tier1": [], "tier2": [], "tier3": []},
            provenance={},
        )
        self.assertEqual(failures, [])
        self.assertEqual(rejections, [])
        self.assertEqual(row["fuel"], "Gas")

    def test_structured_diesel_and_engine_name_support_f350_contract(self):
        item = self.item(fuel_type="diesel", engine_name="6.7 L Turbo Diesel")
        item["name"] = "2022 Ford F-350 XLT"
        row, rejections, failures = parse_listing(
            item,
            config=self.config(fuel="Diesel", engine="6.7L"),
            tiers={"tier1": [], "tier2": [], "tier3": []},
            provenance={},
        )
        self.assertEqual(failures, [])
        self.assertEqual(rejections, [])
        self.assertEqual(row["fuel"], "Diesel")
        self.assertEqual(row["engine"], "6.7L")

    def test_unknown_structured_fuel_still_fails_closed(self):
        row, rejections, failures = parse_listing(
            self.item(fuel_type=""),
            config=self.config(),
            tiers={"tier1": [], "tier2": [], "tier3": []},
            provenance={},
        )
        self.assertEqual(failures, [])
        self.assertIn("fuel_unknown", rejections)
        self.assertEqual(row["fuel"], "Unknown")


if __name__ == "__main__":
    unittest.main()
''',
    encoding="utf-8",
)

(ROOT / "tests" / "test_kijiji_response_diagnostics.py").write_text(
    '''import unittest

from kijiji_response_diagnostics import summarize_kijiji_html


class KijijiResponseDiagnosticsTests(unittest.TestCase):
    def test_sanitized_signature_exposes_response_shape(self):
        summary = summarize_kijiji_html(
            """<html><head><title>Results</title></head><body>
            <script type='application/ld+json'>{\"@type\":\"ItemList\",\"itemListElement\":[]}</script>
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
''',
    encoding="utf-8",
)

print("Applied Kijiji structured-field, diagnostics, and failure-artifact corrections.")
