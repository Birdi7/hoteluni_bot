"""
This file is created for config which is not depends on a particular project
and you won't need to specify them, but vars from here are used in other configs
"""
import pytz
from datetime import date, timedelta
from pathlib import Path

BASE_DIR: Path = Path('.').parent.parent
LOGS_FOLDER: Path = BASE_DIR / "logs"

base_dates_campus_cleaning = {
    1: [date(2019, 4, 19), None, date(2019, 4, 29), date(2019, 5, 8)],
    2: [date(2019, 4, 15), date(2019, 4, 24), date(2019, 5, 3), None],
    3: [date(2019, 4, 17), date(2019, 4, 26), None, date(2019, 5, 6)],
    4: [None, date(2019, 4, 22), date(2019, 5, 1), date(2019, 5, 10)],
}  # campus_number -> some day with cleaning
interval_btw_cleaning = timedelta(days=10)
default_timezone = pytz.timezone("Europe/Moscow")
