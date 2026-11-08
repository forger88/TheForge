import subprocess
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

TOOLS_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIRECTORY))

from document_build import ManagedServices, _url_is_ready


class ManagedServicesTests(unittest.TestCase):
    def test_http_client_errors_still_mean_a_port_is_occupied(self):
        response = urllib.error.HTTPError(
            "http://localhost", 404, "Not Found", {}, None
        )

        with mock.patch("document_build.urllib.request.urlopen", side_effect=response):
            self.assertTrue(_url_is_ready("http://localhost"))

    def test_http_server_errors_are_not_ready(self):
        response = urllib.error.HTTPError(
            "http://localhost", 503, "Unavailable", {}, None
        )

        with mock.patch("document_build.urllib.request.urlopen", side_effect=response):
            self.assertFalse(_url_is_ready("http://localhost"))

    def test_an_unreachable_host_is_not_ready(self):
        self.assertFalse(_url_is_ready("http://127.0.0.1:1"))

    def test_stop_all_ignores_process_exit_races_and_closes_logs(self):
        process = mock.Mock(pid=123)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("service", 10), 0]
        log = mock.Mock()
        services = ManagedServices([], Path("."), {}, Path("."))
        services.processes = [("service", process, log, Path("service.log"))]

        with (
            mock.patch("document_build.os.name", "posix"),
            mock.patch("document_build.signal.SIGKILL", 9, create=True),
            mock.patch(
                "document_build.os.killpg", side_effect=ProcessLookupError, create=True
            ) as killpg,
        ):
            services._stop_all()

        self.assertEqual(2, killpg.call_count)
        self.assertEqual([], services.processes)
        log.close.assert_called_once_with()

    def test_a_service_already_occupying_its_ready_url_refuses_to_start(self):
        services = ManagedServices(
            [
                {
                    "name": "svc",
                    "ready_url": "http://localhost",
                    "command": ["unused"],
                    "cwd": ".",
                }
            ],
            Path("."),
            {},
            Path("."),
        )

        with (
            mock.patch("document_build._url_is_ready", return_value=True),
            self.assertRaises(Exception) as context,
        ):
            services._start(services.services[0])
        self.assertIn("already in use", str(context.exception))


if __name__ == "__main__":
    unittest.main()
