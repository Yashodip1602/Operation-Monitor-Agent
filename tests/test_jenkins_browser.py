from unittest.mock import MagicMock, patch
import pytest

from app.services.jenkins_browser import (
    JenkinsBrowserError,
    JenkinsBrowserManager,
    check_build_status,
    close_browser,
    find_and_open_job,
    open_jenkins_and_login,
    stop_build_via_ui,
    trigger_build_via_ui,
)


@pytest.fixture
def mock_driver():
    with patch("app.services.jenkins_browser.webdriver.Chrome") as mock_chrome:
        driver_instance = MagicMock()
        mock_chrome.return_value = driver_instance
        driver_instance.current_url = "http://localhost:8080/job/test-job/"
        driver_instance.page_source = "<html><body><h1>test-job</h1><div class='build-row'>#1</div></body></html>"
        driver_instance.title = "test-job [Jenkins]"
        yield driver_instance


@patch("app.services.jenkins_browser.ChromeDriverManager")
def test_jenkins_browser_login_flow(mock_cdm, mock_driver):
    manager = JenkinsBrowserManager()
    manager.driver = mock_driver

    # Mock finding login username field and submitting form
    mock_user_elem = MagicMock()
    mock_pass_elem = MagicMock()

    def find_elem_side_effect(by, value):
        if value == "j_username":
            return mock_user_elem
        if value == "j_password":
            return mock_pass_elem
        return MagicMock()

    mock_driver.find_element.side_effect = find_elem_side_effect
    mock_driver.find_elements.return_value = [MagicMock()]

    with patch("app.services.jenkins_browser.WebDriverWait") as mock_wait:
        mock_wait_inst = MagicMock()
        mock_wait.return_value = mock_wait_inst

        # Test login function
        result = manager.open_jenkins_and_login()
        assert result is True
        mock_driver.get.assert_called()


@patch("app.services.jenkins_browser.ChromeDriverManager")
def test_jenkins_browser_trigger_build(mock_cdm, mock_driver):
    manager = JenkinsBrowserManager()
    manager.driver = mock_driver

    with patch.object(manager, "find_and_open_job") as mock_open_job:
        mock_open_job.return_value = "http://localhost:8080/job/my-job/"

        with patch("app.services.jenkins_browser.WebDriverWait") as mock_wait:
            wait_inst = MagicMock()
            mock_wait.return_value = wait_inst
            button_mock = MagicMock()
            wait_inst.until.return_value = button_mock

            with patch.object(manager, "_take_screenshot") as mock_shot:
                mock_shot.return_value = "/screenshots/my-job_build_triggered.png"

                res = manager.trigger_build_via_ui("my-job")
                assert res["job_name"] == "my-job"
                assert res["triggered"] is True
                assert "triggered in the browser" in res["message"]
                button_mock.click.assert_called_once()


@patch("app.services.jenkins_browser.ChromeDriverManager")
def test_jenkins_browser_check_status(mock_cdm, mock_driver):
    manager = JenkinsBrowserManager()
    manager.driver = mock_driver

    with patch.object(manager, "find_and_open_job") as mock_open_job:
        mock_open_job.return_value = "http://localhost:8080/job/my-job/"

        with patch.object(manager, "_take_screenshot") as mock_shot:
            mock_shot.return_value = "/screenshots/my-job_build_status.png"

            res = manager.check_build_status("my-job")
            assert res["job_name"] == "my-job"
            assert "status" in res


@patch("app.services.jenkins_browser.ChromeDriverManager")
def test_jenkins_browser_stop_build(mock_cdm, mock_driver):
    manager = JenkinsBrowserManager()
    manager.driver = mock_driver

    with patch.object(manager, "find_and_open_job") as mock_open_job:
        mock_open_job.return_value = "http://localhost:8080/job/my-job/"

        stop_btn = MagicMock()
        mock_driver.find_elements.return_value = [stop_btn]

        with patch.object(manager, "_take_screenshot") as mock_shot:
            mock_shot.return_value = "/screenshots/my-job_build_stopped.png"

            res = manager.stop_build_via_ui("my-job")
            assert res["job_name"] == "my-job"
            assert res["stopped"] is True
            assert "aborted in the browser" in res["message"]
            stop_btn.click.assert_called_once()
