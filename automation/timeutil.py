"""Date helpers that follow the owner's timezone instead of the host clock (the sandbox may run in UTC)."""

from __future__ import annotations

import datetime as dt
import logging
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEZONE = "America/Los_Angeles"


def local_today() -> dt.date:
    """Return today's date in LOCAL_TIMEZONE, falling back to the host date if the zone is unknown."""
    name = os.getenv("LOCAL_TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        return dt.datetime.now(ZoneInfo(name)).date()
    except (ZoneInfoNotFoundError, ValueError):
        # Windows has no system tz database unless the tzdata package is installed.
        LOGGER.warning("Timezone %s unavailable; using the host date instead", name)
        return dt.date.today()
