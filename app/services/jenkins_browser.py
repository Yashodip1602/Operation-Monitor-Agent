import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from app.config.settings import settings
from app.utils.logger import logger


class JenkinsBrowserError(Exception):
    """Custom exception raised for Jenkins browser automation errors."""
    pass


class JenkinsBrowserManager:
    """
    Manages Selenium Chrome browser session and performs automated UI interactions
    on the Jenkins web dashboard.
    """

    _instance: Optional["JenkinsBrowserManager"] = None

    def __new__(cls) -> "JenkinsBrowserManager":
        if cls._instance is None:
            cls._instance = super(JenkinsBrowserManager, cls).__new__(cls)
            cls._instance.driver = None
        return cls._instance

    @staticmethod
    def find_chrome_binary() -> str:
        """
        Auto-detects or retrieves configured Chrome/Chromium binary path.
        Priority: settings.CHROME_BINARY_PATH -> standard Linux installation paths -> PATH lookup.
        """
        configured_path = getattr(settings, "CHROME_BINARY_PATH", "/usr/bin/chromium-browser")
        if configured_path and Path(configured_path).exists():
            return configured_path

        known_paths = [
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/snap/bin/chromium",
        ]
        for path in known_paths:
            if Path(path).exists():
                return path

        for name in ["chromium-browser", "chromium", "google-chrome", "google-chrome-stable"]:
            found = shutil.which(name)
            if found:
                return found

        return configured_path or "/usr/bin/chromium-browser"

    def check_chrome_binary_on_startup(self) -> bool:
        """Verifies Chrome/Chromium binary exists at configured path during app startup."""
        binary_path = self.find_chrome_binary()
        if Path(binary_path).exists():
            logger.info(f"Chrome/Chromium binary validated successfully at: '{binary_path}'")
            return True
        else:
            logger.error(
                f"ERROR: Cannot find Chrome/Chromium binary at '{binary_path}'. "
                "Jenkins browser automation will fail until installed. "
                "Please run on server: 'sudo apt update && sudo apt install -y chromium-browser chromium-chromedriver'"
            )
            return False

    def get_driver(self) -> webdriver.Chrome:
        """
        Retrieves or initializes a reusable Chrome WebDriver instance using webdriver-manager.
        """
        if self.driver is not None:
            try:
                # Test driver responsiveness
                _ = self.driver.current_url
                return self.driver
            except Exception as e:
                logger.warning(f"Existing WebDriver instance non-responsive, recreating: {e}")
                self.close_browser(force=True)

        binary_path = self.find_chrome_binary()
        logger.info(f"Initializing Selenium Chrome WebDriver using binary at: '{binary_path}'...")

        chrome_options = Options()

        # Headless mode for server / no-GUI environments
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")

        chrome_options.binary_location = binary_path

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(30)
            logger.info(f"Chrome WebDriver successfully initialized with binary '{binary_path}' in headless mode.")
            return self.driver
        except Exception as e:
            logger.error(
                f"Failed to initialize Chrome WebDriver using binary at '{binary_path}': {e}. "
                "Ensure chromium-browser is installed ('sudo apt install -y chromium-browser chromium-chromedriver').",
                exc_info=True,
            )
            raise JenkinsBrowserError(
                f"Failed to launch Chrome browser using binary '{binary_path}' ('{str(e)}'). Verify binary path exists."
            )

    def close_browser(self, force: bool = False) -> None:
        """Closes the Chrome browser session unless KEEP_BROWSER_OPEN is True (and force is False)."""
        if self.driver is not None:
            if force or not settings.KEEP_BROWSER_OPEN:
                try:
                    logger.info("Closing Chrome browser session...")
                    self.driver.quit()
                except Exception as e:
                    logger.warning(f"Error while quitting ChromeDriver: {e}")
                finally:
                    self.driver = None
            else:
                logger.info("KEEP_BROWSER_OPEN is True. Retaining active browser session.")

    def open_jenkins_and_login(self) -> bool:
        """
        Launches Chrome, navigates to Jenkins URL, and performs login if required.

        Returns:
            bool: True if successfully logged in or already authenticated.
        """
        driver = self.get_driver()
        jenkins_url = settings.JENKINS_URL.rstrip("/")
        username = settings.JENKINS_USERNAME
        password = settings.JENKINS_PASSWORD

        logger.info(f"Navigating to Jenkins URL: {jenkins_url}")

        try:
            driver.get(jenkins_url)
        except Exception as e:
            logger.error(f"Failed to load Jenkins URL '{jenkins_url}': {e}")
            raise JenkinsBrowserError(f"Could not connect to Jenkins page at {jenkins_url}.")

        # Check if login form is present
        try:
            wait = WebDriverWait(driver, 5)
            username_field = wait.until(
                EC.presence_of_element_located((By.NAME, "j_username"))
            )
            logger.info("Jenkins login page detected. Attempting login...")

            if not username or not password:
                raise JenkinsBrowserError("Jenkins credentials (JENKINS_USERNAME / JENKINS_PASSWORD) missing in configuration.")

            password_field = driver.find_element(By.NAME, "j_password")

            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)

            # Submit login form
            submit_btn = driver.find_elements(By.NAME, "Submit") or driver.find_elements(By.XPATH, "//button[contains(text(), 'Sign in') or contains(text(), 'Log in')]")
            if submit_btn:
                submit_btn[0].click()
            else:
                password_field.send_keys(Keys.RETURN)

            # Wait for dashboard or main layout to load
            WebDriverWait(driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.ID, "jenkins")),
                    EC.presence_of_element_located((By.ID, "main-panel")),
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'logout')]")),
                )
            )
            logger.info(f"Successfully logged into Jenkins as '{username}'.")
            return True

        except TimeoutException:
            # Login form not found; verify if already logged in or Jenkins has no auth
            if "login" not in driver.current_url.lower():
                logger.info("Already authenticated or Jenkins does not require login.")
                return True
            logger.error("Timeout waiting for Jenkins login elements or authentication response.")
            raise JenkinsBrowserError("Jenkins login failed or timed out.")
        except JenkinsBrowserError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Jenkins login: {e}", exc_info=True)
            raise JenkinsBrowserError(f"Login failed: {str(e)}")

    def find_and_open_job(self, job_name: str) -> str:
        """
        Searches job list or navigates directly to job page, ensuring job exists.

        Args:
            job_name: Name of the target Jenkins job.

        Returns:
            str: Target job page URL.
        """
        self.open_jenkins_and_login()
        driver = self.get_driver()
        jenkins_url = settings.JENKINS_URL.rstrip("/")
        job_url = f"{jenkins_url}/job/{job_name}/"

        logger.info(f"Navigating to job page for '{job_name}' at {job_url}")

        try:
            driver.get(job_url)
            # Check for 404 or missing job header
            wait = WebDriverWait(driver, 5)
            wait.until(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, f"//h1[contains(text(), '{job_name}')]")),
                    EC.presence_of_element_located((By.ID, "main-panel")),
                )
            )

            # Check if 404 page text exists
            if "404" in driver.title or "not found" in driver.page_source.lower():
                # Fallback: try searching on dashboard search box if available
                logger.warning(f"Direct URL for job '{job_name}' returned 404. Attempting dashboard search...")
                return self._search_job_via_dashboard(job_name)

            logger.info(f"Successfully opened job page for '{job_name}'.")
            return driver.current_url

        except TimeoutException:
            logger.warning(f"Timeout loading job page directly. Attempting dashboard search for '{job_name}'...")
            return self._search_job_via_dashboard(job_name)
        except Exception as e:
            logger.error(f"Failed to open job '{job_name}': {e}")
            raise JenkinsBrowserError(f"Failed to find or open job '{job_name}'.")

    def _search_job_via_dashboard(self, job_name: str) -> str:
        """Fallback method to search for a job using the Jenkins search box or dashboard links."""
        driver = self.get_driver()
        jenkins_url = settings.JENKINS_URL.rstrip("/")
        driver.get(jenkins_url)

        try:
            # Check dashboard table links
            job_links = driver.find_elements(By.XPATH, f"//a[contains(@href, '/job/{job_name}') or text()='{job_name}']")
            if job_links:
                job_links[0].click()
                logger.info(f"Found and clicked job link for '{job_name}'.")
                return driver.current_url

            # Try search box
            search_box = driver.find_element(By.ID, "search-box")
            search_box.clear()
            search_box.send_keys(job_name)
            search_box.send_keys(Keys.RETURN)

            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "main-panel"))
            )
            if "404" in driver.title or "not found" in driver.page_source.lower():
                raise JenkinsBrowserError(f"Jenkins job '{job_name}' was not found.")

            logger.info(f"Opened job page via search for '{job_name}'.")
            return driver.current_url
        except Exception as e:
            logger.error(f"Job search failed for '{job_name}': {e}")
            raise JenkinsBrowserError(f"Job '{job_name}' was not found on Jenkins.")

    def trigger_build_via_ui(self, job_name: str) -> Dict[str, Any]:
        """
        Navigates to job page, clicks 'Build Now', and detects build status.

        Args:
            job_name: Name of target Jenkins job.

        Returns:
            Dict containing operation results, job name, status, and screenshot path.
        """
        logger.info(f"Triggering build via UI for job '{job_name}'...")
        self.find_and_open_job(job_name)
        driver = self.get_driver()

        try:
            wait = WebDriverWait(driver, 10)
            # Locate "Build Now" link or button
            build_now_xpath = "//a[contains(@href, 'build') and (contains(text(), 'Build Now') or contains(., 'Build Now') or contains(@title, 'Build') or contains(text(), 'Build') or contains(text(), 'build'))]"
            build_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, build_now_xpath))
            )

            build_button.click()
            logger.info(f"Clicked 'Build Now' for job '{job_name}'.")

            # Wait briefly for build to get queued / start
            time.sleep(2)

            # Observe build status
            status_info = self._observe_current_build_status(job_name)
            screenshot_path = self._take_screenshot(job_name, "build_triggered")

            result = {
                "job_name": job_name,
                "triggered": True,
                "status": status_info.get("status", "QUEUED"),
                "message": f"{job_name} build has been triggered in the browser.",
                "screenshot": screenshot_path,
            }
            logger.info(f"Trigger build flow finished for '{job_name}': {result}")
            return result

        except TimeoutException:
            logger.error(f"'Build Now' button not found or clickable on page for '{job_name}'.")
            raise JenkinsBrowserError(f"Could not find 'Build Now' button for job '{job_name}'.")
        except Exception as e:
            logger.error(f"Failed to trigger build for '{job_name}': {e}", exc_info=True)
            raise JenkinsBrowserError(f"Failed to trigger build for '{job_name}': {str(e)}")

    def check_build_status(self, job_name: str) -> Dict[str, Any]:
        """
        Navigates to job page and reads current build status from DOM.

        Args:
            job_name: Name of target Jenkins job.

        Returns:
            Dict containing job name, build status, last build number, and details.
        """
        logger.info(f"Checking build status via UI for job '{job_name}'...")
        self.find_and_open_job(job_name)
        driver = self.get_driver()

        try:
            status_info = self._observe_current_build_status(job_name)
            screenshot_path = self._take_screenshot(job_name, "build_status")

            status_text = status_info.get("status", "UNKNOWN")
            build_num = status_info.get("build_number")

            msg = f"Job '{job_name}' status is {status_text}."
            if build_num:
                msg = f"Job '{job_name}' build number {build_num} status is {status_text}."

            result = {
                "job_name": job_name,
                "status": status_text,
                "build_number": build_num,
                "message": msg,
                "screenshot": screenshot_path,
            }
            logger.info(f"Build status result for '{job_name}': {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to read build status for '{job_name}': {e}", exc_info=True)
            raise JenkinsBrowserError(f"Failed to read build status for '{job_name}': {str(e)}")

    def _observe_current_build_status(self, job_name: str) -> Dict[str, Any]:
        """Inspects job page DOM for build history icons, status text, and queued/running indicators."""
        driver = self.get_driver()

        status = "UNKNOWN"
        build_number = None

        try:
            # Check for build history widget or build links
            page_text = driver.page_source.lower()

            # Inspect build status icon or text
            if "building" in page_text or "progress" in page_text or driver.find_elements(By.XPATH, "//*[contains(@class, 'anime') or contains(@class, 'progress') or contains(@alt, 'In progress') or contains(@title, 'In progress')]"):
                status = "IN_PROGRESS"
            elif driver.find_elements(By.XPATH, "//*[contains(@class, 'icon-blue') or contains(@alt, 'Success') or contains(@title, 'Success')]"):
                status = "SUCCESS"
            elif driver.find_elements(By.XPATH, "//*[contains(@class, 'icon-red') or contains(@alt, 'Failed') or contains(@title, 'Failed') or contains(@title, 'Failure')]"):
                status = "FAILURE"
            elif driver.find_elements(By.XPATH, "//*[contains(@class, 'icon-aborted') or contains(@alt, 'Aborted') or contains(@title, 'Aborted')]"):
                status = "ABORTED"
            else:
                status = "SUCCESS"  # Default assumption if job loaded clean without errors

            # Try to extract last build number
            build_link = driver.find_elements(By.XPATH, "//a[contains(@href, '/lastBuild') or contains(text(), '#')]")
            if build_link:
                text = build_link[0].text
                if "#" in text:
                    build_number = text.split("#")[-1].strip()

        except Exception as e:
            logger.warning(f"Error observing build DOM status for '{job_name}': {e}")

        return {"status": status, "build_number": build_number}

    def stop_build_via_ui(self, job_name: str) -> Dict[str, Any]:
        """
        Navigates to running build or job page and clicks Abort/Stop button.

        Args:
            job_name: Name of target Jenkins job.

        Returns:
            Dict containing operation results and status.
        """
        logger.info(f"Stopping build via UI for job '{job_name}'...")
        self.find_and_open_job(job_name)
        driver = self.get_driver()

        try:
            # Check for stop / abort button on job page or last build page
            stop_xpath = "//a[contains(@href, 'stop') or contains(@href, 'kill') or contains(@href, 'abort') or contains(text(), 'Abort') or contains(text(), 'Cancel') or contains(@title, 'Abort')]"
            stop_buttons = driver.find_elements(By.XPATH, stop_xpath)

            if not stop_buttons:
                # Try navigating to last build page
                jenkins_url = settings.JENKINS_URL.rstrip("/")
                driver.get(f"{jenkins_url}/job/{job_name}/lastBuild/")
                stop_buttons = driver.find_elements(By.XPATH, stop_xpath)

            if stop_buttons:
                stop_buttons[0].click()
                logger.info(f"Clicked stop/abort button for job '{job_name}'.")

                # Handle confirmation dialog if present
                try:
                    alert = driver.switch_to.alert
                    alert.accept()
                except Exception:
                    pass

                time.sleep(1)
                screenshot_path = self._take_screenshot(job_name, "build_stopped")

                result = {
                    "job_name": job_name,
                    "stopped": True,
                    "message": f"Build for job '{job_name}' has been aborted in the browser.",
                    "screenshot": screenshot_path,
                }
                logger.info(f"Stop build result for '{job_name}': {result}")
                return result
            else:
                logger.info(f"No active running build to stop for job '{job_name}'.")
                screenshot_path = self._take_screenshot(job_name, "no_running_build")
                return {
                    "job_name": job_name,
                    "stopped": False,
                    "message": f"No active build was found running for job '{job_name}'.",
                    "screenshot": screenshot_path,
                }

        except Exception as e:
            logger.error(f"Failed to stop build for '{job_name}': {e}", exc_info=True)
            raise JenkinsBrowserError(f"Failed to stop build for '{job_name}': {str(e)}")

    def _take_screenshot(self, job_name: str, action: str) -> Optional[str]:
        """Saves a screenshot of the current browser state for logging/debugging."""
        if not self.driver:
            return None
        try:
            timestamp = int(time.time())
            filename = f"{job_name}_{action}_{timestamp}.png"
            filepath = settings.SCREENSHOT_DIR / filename
            self.driver.save_screenshot(str(filepath))
            logger.info(f"Saved build action screenshot to: {filepath}")
            return f"/screenshots/{filename}"
        except Exception as e:
            logger.warning(f"Failed to capture screenshot: {e}")
            return None


# Module-level singleton instance
jenkins_browser_manager = JenkinsBrowserManager()


# Standalone functions required by prompt
def open_jenkins_and_login() -> bool:
    """Launches Chrome, navigates to Jenkins, logs in."""
    return jenkins_browser_manager.open_jenkins_and_login()


def find_and_open_job(job_name: str) -> str:
    """Searches job list, clicks into the job page."""
    return jenkins_browser_manager.find_and_open_job(job_name)


def trigger_build_via_ui(job_name: str) -> Dict[str, Any]:
    """Full flow: login -> find job -> click Build Now."""
    return jenkins_browser_manager.trigger_build_via_ui(job_name)


def check_build_status(job_name: str) -> Dict[str, Any]:
    """Navigates to job page, reads current build status from the DOM."""
    return jenkins_browser_manager.check_build_status(job_name)


def stop_build_via_ui(job_name: str) -> Dict[str, Any]:
    """Navigates to running build page, clicks Abort/Stop button."""
    return jenkins_browser_manager.stop_build_via_ui(job_name)


def close_browser(force: bool = False) -> None:
    """Closes browser session."""
    jenkins_browser_manager.close_browser(force=force)
