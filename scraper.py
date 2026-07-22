"""Compatibility entry point for the direct AutoTrader adapter.

The active workflow calls ``autotrader_run.py``. This module remains only so older
manual commands fail forward into the governed schema-v2 adapter rather than the
retired ranking/config-mutation implementation.
"""
from autotrader_adapter import main


if __name__ == "__main__":
    raise SystemExit(main())
