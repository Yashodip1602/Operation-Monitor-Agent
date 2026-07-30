import jenkins
from typing import Any, Dict, List, Optional
from app.config.settings import settings
from app.utils.logger import logger


class JenkinsClientError(Exception):
    """Custom exception raised for Jenkins integration errors."""
    pass


class JenkinsClient:
    """Singleton service for managing Jenkins operations via python-jenkins."""

    _instance: Optional["JenkinsClient"] = None
    _server: Optional[jenkins.Jenkins] = None

    def __new__(cls) -> "JenkinsClient":
        if cls._instance is None:
            cls._instance = super(JenkinsClient, cls).__new__(cls)
        return cls._instance

    def _get_server(self) -> jenkins.Jenkins:
        """
        Retrieves or initializes the Jenkins server connection.
        """
        if self._server is not None:
            return self._server

        url = settings.JENKINS_URL
        username = settings.JENKINS_USERNAME
        password = settings.JENKINS_PASSWORD

        if not url:
            raise JenkinsClientError("Jenkins URL is not configured in environment settings.")

        try:
            logger.info(f"Connecting to Jenkins server at {url} (user: {username or 'anonymous'})")
            server = jenkins.Jenkins(
                url=url,
                username=username if username else None,
                password=password if password else None,
            )
            version = server.get_version()
            logger.info(f"Successfully connected to Jenkins server (version: {version})")
            self._server = server
            return self._server
        except Exception as e:
            logger.error(f"Failed to connect to Jenkins server at {url}: {e}")
            raise JenkinsClientError(f"Jenkins connection failed: {str(e)}")

    def reset_connection(self) -> None:
        """Resets the cached server instance."""
        self._server = None

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """
        Lists all Jenkins jobs on the server.

        Returns:
            List of dictionaries with job details ('name', 'url', 'color', 'status').
        """
        try:
            server = self._get_server()
            logger.info("Fetching list of all Jenkins jobs...")
            jobs = server.get_jobs()
            
            job_list = []
            for job in jobs:
                color = job.get("color", "")
                status = "UNKNOWN"
                if "anime" in color:
                    status = "IN_PROGRESS"
                elif "blue" in color:
                    status = "SUCCESS"
                elif "red" in color:
                    status = "FAILURE"
                elif "disabled" in color:
                    status = "DISABLED"

                job_list.append({
                    "name": job.get("name"),
                    "url": job.get("url"),
                    "color": color,
                    "status": status,
                })

            logger.info(f"Retrieved {len(job_list)} Jenkins jobs.")
            return job_list
        except jenkins.JenkinsException as je:
            logger.error(f"Jenkins API Error in get_all_jobs: {je}")
            raise JenkinsClientError(f"Jenkins API Error: {str(je)}")
        except Exception as e:
            logger.error(f"Failed to fetch Jenkins jobs: {e}", exc_info=True)
            raise JenkinsClientError(f"Failed to fetch Jenkins jobs: {str(e)}")

    def trigger_build(
        self,
        job_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Triggers a build for the specified Jenkins job.

        Args:
            job_name: Name of the Jenkins job.
            parameters: Optional parameter dictionary for parameterized builds.

        Returns:
            Dict containing action confirmation and triggered job details.
        """
        try:
            server = self._get_server()
            if not server.job_exists(job_name):
                raise JenkinsClientError(f"Jenkins job '{job_name}' does not exist.")

            logger.info(f"Triggering build for Jenkins job '{job_name}' (params: {parameters})")
            if parameters:
                server.build_job(job_name, parameters=parameters)
            else:
                server.build_job(job_name)

            job_info = server.get_job_info(job_name)
            next_build = job_info.get("nextBuildNumber")

            logger.info(f"Build successfully triggered for job '{job_name}' (Next build #: {next_build})")
            return {
                "job_name": job_name,
                "triggered": True,
                "next_build_number": next_build,
                "message": f"Build triggered successfully for job '{job_name}'.",
            }
        except jenkins.NotFoundException:
            logger.error(f"Job '{job_name}' not found on Jenkins server.")
            raise JenkinsClientError(f"Job '{job_name}' was not found.")
        except jenkins.JenkinsException as je:
            logger.error(f"Jenkins API Error in trigger_build for '{job_name}': {je}")
            raise JenkinsClientError(f"Failed to trigger build for '{job_name}': {str(je)}")
        except Exception as e:
            logger.error(f"Failed to trigger build for '{job_name}': {e}", exc_info=True)
            raise JenkinsClientError(f"Failed to trigger build for '{job_name}': {str(e)}")

    def get_job_status(self, job_name: str) -> Dict[str, Any]:
        """
        Retrieves the status of the last build for a specified job.

        Args:
            job_name: Name of the Jenkins job.

        Returns:
            Dict containing job name, last build number, build status, and details.
        """
        try:
            server = self._get_server()
            if not server.job_exists(job_name):
                raise JenkinsClientError(f"Jenkins job '{job_name}' does not exist.")

            logger.info(f"Fetching job status for '{job_name}'...")
            job_info = server.get_job_info(job_name)
            last_build = job_info.get("lastBuild")

            if not last_build:
                logger.info(f"No builds found for job '{job_name}'.")
                return {
                    "job_name": job_name,
                    "last_build_number": None,
                    "status": "NO_BUILDS",
                    "building": False,
                    "message": f"Job '{job_name}' has no execution history.",
                }

            build_number = last_build.get("number")
            build_info = server.get_build_info(job_name, build_number)

            is_building = build_info.get("building", False)
            result = build_info.get("result")

            status = "IN_PROGRESS" if is_building else (result or "UNKNOWN")
            duration_s = round(build_info.get("duration", 0) / 1000, 2)

            logger.info(f"Job '{job_name}' build #{build_number} status: {status}")
            return {
                "job_name": job_name,
                "last_build_number": build_number,
                "status": status,
                "building": is_building,
                "result": result,
                "duration_seconds": duration_s,
                "message": f"Job '{job_name}' build #{build_number} status is {status}.",
            }
        except jenkins.NotFoundException:
            logger.error(f"Job '{job_name}' not found on Jenkins server.")
            raise JenkinsClientError(f"Job '{job_name}' was not found.")
        except jenkins.JenkinsException as je:
            logger.error(f"Jenkins API Error in get_job_status for '{job_name}': {je}")
            raise JenkinsClientError(f"Failed to get job status for '{job_name}': {str(je)}")
        except Exception as e:
            logger.error(f"Failed to get status for '{job_name}': {e}", exc_info=True)
            raise JenkinsClientError(f"Failed to get status for '{job_name}': {str(e)}")

    def stop_build(self, job_name: str, build_number: Optional[int] = None) -> Dict[str, Any]:
        """
        Aborts/stops a running build for the specified Jenkins job.

        Args:
            job_name: Name of the Jenkins job.
            build_number: Optional build number to stop. Defaults to the last active build.

        Returns:
            Dict containing outcome of the stop request.
        """
        try:
            server = self._get_server()
            if not server.job_exists(job_name):
                raise JenkinsClientError(f"Jenkins job '{job_name}' does not exist.")

            target_build_number = build_number
            if target_build_number is None:
                job_info = server.get_job_info(job_name)
                last_build = job_info.get("lastBuild")
                if not last_build:
                    raise JenkinsClientError(f"No active or past builds found for job '{job_name}'.")
                target_build_number = last_build.get("number")

            logger.info(f"Stopping build #{target_build_number} for job '{job_name}'...")
            server.stop_build(job_name, target_build_number)

            logger.info(f"Successfully sent stop request for job '{job_name}' build #{target_build_number}.")
            return {
                "job_name": job_name,
                "build_number": target_build_number,
                "stopped": True,
                "message": f"Build #{target_build_number} for job '{job_name}' has been stopped.",
            }
        except jenkins.NotFoundException:
            logger.error(f"Job '{job_name}' not found on Jenkins server.")
            raise JenkinsClientError(f"Job '{job_name}' was not found.")
        except jenkins.JenkinsException as je:
            logger.error(f"Jenkins API Error in stop_build for '{job_name}': {je}")
            raise JenkinsClientError(f"Failed to stop build for '{job_name}': {str(je)}")
        except Exception as e:
            logger.error(f"Failed to stop build for '{job_name}': {e}", exc_info=True)
            raise JenkinsClientError(f"Failed to stop build for '{job_name}': {str(e)}")

    def get_console_output(
        self,
        job_name: str,
        build_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Fetches console output logs for a job's build.

        Args:
            job_name: Name of the Jenkins job.
            build_number: Optional build number. Defaults to last build.

        Returns:
            Dict containing console logs text and build metadata.
        """
        try:
            server = self._get_server()
            if not server.job_exists(job_name):
                raise JenkinsClientError(f"Jenkins job '{job_name}' does not exist.")

            target_build_number = build_number
            if target_build_number is None:
                job_info = server.get_job_info(job_name)
                last_build = job_info.get("lastBuild")
                if not last_build:
                    raise JenkinsClientError(f"No builds found for job '{job_name}'.")
                target_build_number = last_build.get("number")

            logger.info(f"Fetching console output for job '{job_name}' build #{target_build_number}...")
            console_log = server.get_build_console_output(job_name, target_build_number)

            snippet = console_log[-1000:] if len(console_log) > 1000 else console_log

            logger.info(f"Retrieved console logs for job '{job_name}' build #{target_build_number}.")
            return {
                "job_name": job_name,
                "build_number": target_build_number,
                "console_log": console_log,
                "snippet": snippet,
                "message": f"Retrieved console logs for job '{job_name}' build #{target_build_number}.",
            }
        except jenkins.NotFoundException:
            logger.error(f"Job '{job_name}' not found on Jenkins server.")
            raise JenkinsClientError(f"Job '{job_name}' was not found.")
        except jenkins.JenkinsException as je:
            logger.error(f"Jenkins API Error in get_console_output for '{job_name}': {je}")
            raise JenkinsClientError(f"Failed to retrieve logs for '{job_name}': {str(je)}")
        except Exception as e:
            logger.error(f"Failed to get console logs for '{job_name}': {e}", exc_info=True)
            raise JenkinsClientError(f"Failed to retrieve logs for '{job_name}': {str(e)}")


jenkins_client = JenkinsClient()
