"""Compatibility entry point for governed Kijiji collection.

The active workflow calls ``kijiji_run.py`` directly. Older manual commands that
still invoke ``kijiji_scraper.py`` are forwarded through the same bounded runtime,
source status, adapter evidence, and canonical-evidence path rather than bypassing
those controls.
"""
from kijiji_run import main


if __name__ == "__main__":
    raise SystemExit(main())
