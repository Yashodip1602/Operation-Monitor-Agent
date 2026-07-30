import pytest
from app.services.intent_parser import IntentParser, IntentType


@pytest.fixture
def parser():
    return IntentParser()


def test_parse_trigger_build(parser):
    res = parser.parse("Trigger build for my-project")
    assert res.intent == IntentType.TRIGGER_BUILD
    assert res.job_name == "my-project"


def test_parse_start_build_alternative(parser):
    res = parser.parse("Start build deploy-app")
    assert res.intent == IntentType.TRIGGER_BUILD
    assert res.job_name == "deploy-app"


def test_parse_get_status(parser):
    res = parser.parse("What is the status of my-project")
    assert res.intent == IntentType.GET_STATUS
    assert res.job_name == "my-project"


def test_parse_check_status(parser):
    res = parser.parse("Check status for test-runner")
    assert res.intent == IntentType.GET_STATUS
    assert res.job_name == "test-runner"


def test_parse_stop_build(parser):
    res = parser.parse("Stop build for my-project")
    assert res.intent == IntentType.STOP_BUILD
    assert res.job_name == "my-project"


def test_parse_abort_job(parser):
    res = parser.parse("Abort job backend-api")
    assert res.intent == IntentType.STOP_BUILD
    assert res.job_name == "backend-api"


def test_parse_list_jobs(parser):
    res = parser.parse("List all jobs")
    assert res.intent == IntentType.LIST_JOBS
    assert res.job_name is None


def test_parse_get_console_logs(parser):
    res = parser.parse("Show console logs for build-app")
    assert res.intent == IntentType.GET_LOGS
    assert res.job_name == "build-app"


def test_known_jobs_matching(parser):
    known_jobs = ["my-project", "deploy-service", "analytics-pipeline"]
    res = parser.parse("Trigger build for my project", known_jobs=known_jobs)
    assert res.intent == IntentType.TRIGGER_BUILD
    assert res.job_name == "my-project"


def test_parse_unknown(parser):
    res = parser.parse("Hello standard world")
    assert res.intent == IntentType.UNKNOWN
