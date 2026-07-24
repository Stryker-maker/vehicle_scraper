import unittest

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
