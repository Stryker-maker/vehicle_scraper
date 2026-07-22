import csv
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from phase1_pipeline import (
    dedupe_history_observations_for_date, expected_output_path,
    remove_history_observations_for_date, row_quality_warnings, run_source, write_json,
)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config_test.json"
        self.config = {
            "schema_version": 2,
            "vehicle_key": "test_vehicle",
            "make": "Test",
            "model": "Vehicle",
            "criteria": {
                "min_year": 2000, "max_year": 2030, "max_price_cad": 100000,
                "fuel": "Gas", "engine": "",
            },
            "origin": {
                "home_city": "Red Deer, AB", "home_coords": [52.2681, -113.8112],
                "max_distance_km": 800,
            },
            "sources": {
                "autotrader": {
                    "make": "test", "model": "vehicle",
                    "search_locations": ["Original, AB"],
                },
                "kijiji": {
                    "make": "Test", "model": "Vehicle",
                    "search_locations": ["Original, AB"],
                },
            },
        }
        self.config_path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def collector(self):
        path = self.root / "collector.py"
        path.write_text("""
import argparse,csv,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--source',required=True);a=p.parse_args()
c=Path(a.config);cfg=json.loads(c.read_text());assert cfg['max_results']>200
assert 'ranking_weights' in cfg
assert cfg['search_locations']==['Original, AB']
cfg['search_locations']=['Mutated, AB'];c.write_text(json.dumps(cfg))
out=Path('data')/cfg['vehicle_key']/'latest'/f"{cfg['vehicle_key']}_{a.source}_latest.csv";out.parent.mkdir(parents=True,exist_ok=True)
f=['listing_id','url','source','price','mileage','location','distance_km']
with out.open('w',newline='',encoding='utf-8') as h:
 w=csv.DictWriter(h,fieldnames=f);w.writeheader()
 for i in range(200): w.writerow({'listing_id':str(i),'url':f'https://example.invalid/2020-{i}','source':'AutoTrader','price':'1','mileage':'1','location':'A','distance_km':'1'})
""", encoding="utf-8")
        return path

    def test_uncapped_200_rows_and_config_isolation(self):
        original = self.config_path.read_bytes()
        script = self.collector()
        status = run_source(
            root=self.root, source="autotrader", config_path=self.config_path,
            command=[sys.executable, str(script), "--config", "config_test.json", "--source", "autotrader"],
            run_id="run-1",
        )
        self.assertEqual(status["row_count"], 200)
        self.assertTrue(status["row_cap_disabled"])
        self.assertEqual(status["effective_max_results"], "unbounded")
        self.assertIsNone(status["configured_max_results"])
        self.assertEqual(status["configuration_schema_version"], 2)
        self.assertEqual(status["runtime_config_projection"], "legacy_collector_v1")
        self.assertFalse(status["approved_config_contains_legacy_controls"])
        self.assertEqual(self.config_path.read_bytes(), original)
        self.assertTrue(status["config_isolated"])

    def test_kijiji_runtime_records_distance_bypass_and_3000_rows(self):
        script = self.root / "kijiji_collector.py"
        script.write_text("""
import argparse,csv,json,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args()
assert os.environ['PHASE1_KIJIJI_DISTANCE_DISABLED']=='1'
cfg=json.loads(Path(a.config).read_text())
assert cfg['search_locations']==['Original, AB']
out=Path('data')/cfg['vehicle_key']/'latest'/f"{cfg['vehicle_key']}_kijiji_latest.csv";out.parent.mkdir(parents=True,exist_ok=True)
f=['listing_id','url','source','price','mileage','location','distance_km']
with out.open('w',newline='',encoding='utf-8') as h:
 w=csv.DictWriter(h,fieldnames=f);w.writeheader()
 for i in range(3000): w.writerow({'listing_id':str(i),'url':f'https://www.kijiji.ca/v-cars-trucks/calgary/x/{i}','source':'Kijiji','price':'1','mileage':'1','location':'Search Origin','distance_km':''})
""", encoding="utf-8")
        status = run_source(
            root=self.root, source="kijiji", config_path=self.config_path,
            command=[sys.executable, str(script), "--config", "config_test.json"],
            run_id="run-1",
        )
        self.assertEqual(status["current_row_count"], 3000)
        self.assertTrue(status["distance_processing_disabled"])
        self.assertTrue(status["distance_filter_disabled"])
        self.assertTrue(status["legacy_source_ranking_disabled"])

    def test_stale_output_is_degraded_and_not_current(self):
        out = expected_output_path(self.root, self.config, "autotrader")
        out.parent.mkdir(parents=True)
        out.write_text("listing_id,url,source,price,mileage,location,distance_km\n1,u,s,1,1,a,1\n")
        status = run_source(
            root=self.root, source="autotrader", config_path=self.config_path,
            command=[sys.executable, "-c", "pass"], run_id="run-1",
        )
        self.assertEqual(status["execution_status"], "degraded")
        self.assertIn("no_fresh_output", status["failure_reasons"])
        self.assertEqual(status["current_row_count"], 0)
        self.assertEqual(status["stale_row_count"], 1)
        self.assertEqual(status["data_quality_status"], "not_evaluated_stale_output")

    def test_failure_is_recorded(self):
        status = run_source(
            root=self.root, source="kijiji", config_path=self.config_path,
            command=[sys.executable, "-c", "raise SystemExit(7)"], run_id="run-1",
        )
        self.assertEqual(status["execution_status"], "failed")
        self.assertEqual(status["exit_code"], 7)

    def test_timeout_is_bounded(self):
        started = time.monotonic()
        status = run_source(
            root=self.root, source="autotrader", config_path=self.config_path,
            command=[sys.executable, "-c", "import time;time.sleep(2)"],
            run_id="run-1", timeout_seconds=.05,
        )
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(status["execution_status"], "timed_out")

    def test_history_helpers_are_idempotent(self):
        path = self.root / "history.json"
        write_json(path, {"x": [{"date":"old","price":3},{"date":"today","price":2},{"date":"today","price":1}]})
        self.assertEqual(remove_history_observations_for_date(path, "today"), 2)
        data = json.loads(path.read_text())
        data["x"] += [{"date":"today","price":2},{"date":"today","price":1}]
        write_json(path, data)
        self.assertEqual(dedupe_history_observations_for_date(path, "today"), 1)
        self.assertEqual(json.loads(path.read_text())["x"][-1]["price"], 1)

    def test_failed_run_restores_history(self):
        path = self.root / "data/test_vehicle/price_history_autotrader.json"
        write_json(path, {"x": [{"date":"2026-07-21","price":1}]})
        original = path.read_bytes()
        run_source(
            root=self.root, source="autotrader", config_path=self.config_path,
            command=[sys.executable, "-c", "raise SystemExit(2)"], run_id="run-1",
        )
        self.assertEqual(path.read_bytes(), original)

    def test_quality_warning_rules(self):
        warnings = row_quality_warnings(
            {"year":"2014","mileage":"1","url":"https://x/2011-dodge"},
            "Kijiji", current_year=2026,
        )
        self.assertIn("unverified_kijiji_location", warnings)
        self.assertIn("url_year_conflicts_with_parsed_year", warnings)
        self.assertIn("suspiciously_low_mileage", warnings)


if __name__ == "__main__":
    unittest.main()
