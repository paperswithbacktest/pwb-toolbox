from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo  # OK to keep if you like
import pendulum  # pendulum is simpler for tz-aware dates
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.timetables.trigger import CronTriggerTimetable  # <-- NEW

PROJECT_ROOT = Path(__file__).resolve().parents[2]

NY = pendulum.timezone("America/New_York")

with DAG(
    dag_id="ib_execute",
    start_date=datetime(2024, 1, 1, tzinfo=NY),  # tz-aware start date
    schedule=CronTriggerTimetable(  # <-- put the cron + tz here
        "35 9 * * 1-5", timezone=NY  # 09:35 Mon-Fri
    ),
    catchup=False,
    tags=["pwb", "ib"],
) as dag:
    BashOperator(
        task_id="run_execute_script",
        bash_command=(
            f"cd {PROJECT_ROOT} && "
            f"export PYTHONPATH={PROJECT_ROOT}:$PYTHONPATH && "
            "python -m src.execute"
        ),
    )
