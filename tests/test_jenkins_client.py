from unittest.mock import MagicMock, patch
import pytest
import jenkins

from app.services.jenkins_client import JenkinsClient, JenkinsClientError


@pytest.fixture
def jenkins_client_instance():
    client = JenkinsClient()
    client.reset_connection()
    yield client
    client.reset_connection()


@patch("app.services.jenkins_client.jenkins.Jenkins")
def test_jenkins_connection_success(mock_jenkins, jenkins_client_instance):
    mock_server = MagicMock()
    mock_server.get_version.return_value = "2.440.1"
    mock_jenkins.return_value = mock_server

    server = jenkins_client_instance._get_server()
    assert server is mock_server
    mock_server.get_version.assert_called_once()


@patch("app.services.jenkins_client.jenkins.Jenkins")
def test_jenkins_connection_failure(mock_jenkins, jenkins_client_instance):
    mock_jenkins.side_effect = Exception("Connection refused")

    with pytest.raises(JenkinsClientError) as exc_info:
        jenkins_client_instance._get_server()

    assert "Jenkins connection failed" in str(exc_info.value)


@patch("app.services.jenkins_client.jenkins.Jenkins")
def test_get_all_jobs(mock_jenkins, jenkins_client_instance):
    mock_server = MagicMock()
    mock_server.get_version.return_value = "2.440.1"
    mock_server.get_jobs.return_value = [
        {"name": "build-app", "url": "http://localhost:8080/job/build-app/", "color": "blue"},
        {"name": "deploy-app", "url": "http://localhost:8080/job/deploy-app/", "color": "red"},
        {"name": "test-app", "url": "http://localhost:8080/job/test-app/", "color": "blue_anime"},
    ]
    mock_jenkins.return_value = mock_server

    jobs = jenkins_client_instance.get_all_jobs()
    assert len(jobs) == 3
    assert jobs[0]["name"] == "build-app"
    assert jobs[0]["status"] == "SUCCESS"
    assert jobs[1]["status"] == "FAILURE"
    assert jobs[2]["status"] == "IN_PROGRESS"


@patch("app.services.jenkins_client.jenkins.Jenkins")
def test_trigger_build_success(mock_jenkins, jenkins_client_instance):
    mock_server = MagicMock()
    mock_server.get_version.return_value = "2.440.1"
    mock_server.job_exists.return_value = True
    mock_server.get_job_info.return_value = {"nextBuildNumber": 42}
    mock_jenkins.return_value = mock_server

    res = jenkins_client_instance.trigger_build("build-app", parameters={"ENV": "prod"})
    assert res["triggered"] is True
    assert res["job_name"] == "build-app"
    assert res["next_build_number"] == 42
    mock_server.build_job.assert_called_once_with("build-app", parameters={"ENV": "prod"})


@patch("app.services.jenkins_client.jenkins.Jenkins")
def test_trigger_build_job_not_found(mock_jenkins, jenkins_client_instance):
    mock_server = MagicMock()
    mock_server.get_version.return_value = "2.440.1"
    mock_server.job_exists.return_value = False
    mock_jenkins.return_value = mock_server

    with pytest.raises(JenkinsClientError) as exc:
        jenkins_client_instance.trigger_build("non-existent-job")
    assert "does not exist" in str(exc.value)


@patch("app.services.jenkins_client.jenkins.Jenkins")
def test_get_job_status(mock_jenkins, jenkins_client_instance):
    mock_server = MagicMock()
    mock_server.get_version.return_value = "2.440.1"
    mock_server.job_exists.return_value = True
    mock_server.get_job_info.return_value = {"lastBuild": {"number": 15}}
    mock_server.get_build_info.return_value = {
        "building": False,
        "result": "SUCCESS",
        "duration": 5000,
    }
    mock_jenkins.return_value = mock_server

    res = jenkins_client_instance.get_job_status("build-app")
    assert res["status"] == "SUCCESS"
    assert res["last_build_number"] == 15
    assert res["building"] is False


@patch("app.services.jenkins_client.jenkins.Jenkins")
def test_stop_build(mock_jenkins, jenkins_client_instance):
    mock_server = MagicMock()
    mock_server.get_version.return_value = "2.440.1"
    mock_server.job_exists.return_value = True
    mock_server.get_job_info.return_value = {"lastBuild": {"number": 12}}
    mock_jenkins.return_value = mock_server

    res = jenkins_client_instance.stop_build("build-app")
    assert res["stopped"] is True
    assert res["build_number"] == 12
    mock_server.stop_build.assert_called_once_with("build-app", 12)


@patch("app.services.jenkins_client.jenkins.Jenkins")
def test_get_console_output(mock_jenkins, jenkins_client_instance):
    mock_server = MagicMock()
    mock_server.get_version.return_value = "2.440.1"
    mock_server.job_exists.return_value = True
    mock_server.get_job_info.return_value = {"lastBuild": {"number": 8}}
    mock_server.get_build_console_output.return_value = "Finished: SUCCESS\nLog contents here."
    mock_jenkins.return_value = mock_server

    res = jenkins_client_instance.get_console_output("build-app")
    assert res["job_name"] == "build-app"
    assert "Finished: SUCCESS" in res["console_log"]
