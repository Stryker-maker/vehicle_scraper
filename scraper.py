"""Compatibility entry point for governed AutoTrader collection.

The active workflow calls ``autotrader_run.py`` directly. Older manual commands that
still invoke ``scraper.py`` are forwarded through the same bounded runtime, source
status, and canonical-evidence path rather than bypassing those controls.
"""
from autotrader_run import main


if __name__ == "__main__":
    raise SystemExit(main())
