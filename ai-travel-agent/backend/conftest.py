import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))


@pytest.fixture(autouse=True)
def no_plan_run_telemetry():
    """Unit runs must not land in the plan_runs comparison data."""
    from app.config import settings

    original = settings.record_plan_runs
    settings.record_plan_runs = False
    yield
    settings.record_plan_runs = original
