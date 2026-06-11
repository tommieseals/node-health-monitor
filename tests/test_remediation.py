"""Tests for the auto-remediation handler (subprocess mocked)."""

import subprocess
from unittest import mock

import pytest

from node_health_monitor.config import NodeConfig, RemediationConfig, Thresholds
from node_health_monitor.models import NodeHealth, ServiceStatus
from node_health_monitor.remediation import RemediationHandler

THRESHOLDS = {"memory": (80.0, 90.0), "disk": (80.0, 90.0), "load": (4.0, 8.0)}


def make_health(memory_percent=50.0, disk_percent=40.0, load=1.0, services=None):
    return NodeHealth(
        name="web-server",
        host="192.168.1.10",
        platform="linux",
        reachable=True,
        memory_percent=memory_percent,
        disk_percent=disk_percent,
        load_average=(load, load, load),
        cpu_count=4,
        services=services or [],
        thresholds=THRESHOLDS,
    )


def make_node():
    return NodeConfig(name="web-server", platform="linux", local=True, thresholds=Thresholds())


def completed_process(returncode=0, stdout="done", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestRemediationHandler:
    def test_disabled_config_runs_nothing(self):
        handler = RemediationHandler(RemediationConfig(enabled=False), make_node())

        with mock.patch("node_health_monitor.remediation.handler.subprocess.run") as run:
            results = handler.handle(make_health(memory_percent=99.0))

        assert results == []
        run.assert_not_called()

    def test_healthy_node_runs_nothing(self):
        config = RemediationConfig(enabled=True, on_high_memory="cleanup-memory.sh")
        handler = RemediationHandler(config, make_node())

        with mock.patch("node_health_monitor.remediation.handler.subprocess.run") as run:
            results = handler.handle(make_health(memory_percent=50.0))

        assert results == []
        run.assert_not_called()

    def test_critical_memory_triggers_hook_without_shell(self):
        config = RemediationConfig(enabled=True, on_high_memory="cleanup --target memory")
        handler = RemediationHandler(config, make_node())

        with mock.patch(
            "node_health_monitor.remediation.handler.subprocess.run",
            return_value=completed_process(stdout="cleaned"),
        ) as run:
            results = handler.handle(make_health(memory_percent=95.0))

        assert results == [("high_memory", True, "cleaned")]
        run.assert_called_once()
        # Command string is shlex-split into an argv list; no shell involved
        assert run.call_args.args[0] == ["cleanup", "--target", "memory"]
        assert run.call_args.kwargs["shell"] is False

    def test_environment_variables_passed_to_command(self):
        config = RemediationConfig(
            enabled=True,
            on_service_down={"nginx": "systemctl restart nginx"},
        )
        handler = RemediationHandler(config, make_node())
        health = make_health(services=[ServiceStatus(name="nginx", running=False)])

        with mock.patch(
            "node_health_monitor.remediation.handler.subprocess.run",
            return_value=completed_process(),
        ) as run:
            results = handler.handle(health)

        assert results == [("restart_nginx", True, "done")]
        env = run.call_args.kwargs["env"]
        assert env["NHM_NODE_NAME"] == "web-server"
        assert env["NHM_NODE_HOST"] == "192.168.1.10"
        assert env["NHM_SERVICE"] == "nginx"
        assert env["NHM_ACTION"] == "service_down:nginx"

    def test_existing_script_file_is_executed_directly(self, tmp_path):
        script = tmp_path / "cleanup-disk.sh"
        script.write_text("#!/bin/sh\necho cleaned\n")
        config = RemediationConfig(
            enabled=True,
            scripts_dir=str(tmp_path),
            on_high_disk="cleanup-disk.sh",
        )
        handler = RemediationHandler(config, make_node())

        with mock.patch(
            "node_health_monitor.remediation.handler.subprocess.run",
            return_value=completed_process(),
        ) as run:
            handler.handle(make_health(disk_percent=95.0))

        assert run.call_args.args[0] == [str(script)]

    def test_dry_run_executes_nothing(self):
        config = RemediationConfig(enabled=True, on_high_load="reboot-something")
        handler = RemediationHandler(config, make_node(), dry_run=True)

        with mock.patch("node_health_monitor.remediation.handler.subprocess.run") as run:
            results = handler.handle(make_health(load=10.0))

        run.assert_not_called()
        assert len(results) == 1
        action, success, message = results[0]
        assert action == "high_load"
        assert success is True
        assert message.startswith("Dry run")

    def test_failing_command_reports_failure(self):
        config = RemediationConfig(enabled=True, on_high_memory="cleanup")
        handler = RemediationHandler(config, make_node())

        with mock.patch(
            "node_health_monitor.remediation.handler.subprocess.run",
            return_value=completed_process(returncode=1, stdout="", stderr="no permission"),
        ):
            results = handler.handle(make_health(memory_percent=95.0))

        assert results == [("high_memory", False, "no permission")]

    def test_timeout_reports_failure(self):
        config = RemediationConfig(enabled=True, on_high_memory="cleanup")
        handler = RemediationHandler(config, make_node())

        with mock.patch(
            "node_health_monitor.remediation.handler.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="cleanup", timeout=60),
        ):
            results = handler.handle(make_health(memory_percent=95.0))

        action, success, message = results[0]
        assert success is False
        assert "timed out" in message

    def test_missing_command_reports_failure(self):
        config = RemediationConfig(enabled=True, on_high_memory="definitely-not-a-real-cmd-12345")
        handler = RemediationHandler(config, make_node())

        results = handler.handle(make_health(memory_percent=95.0))

        action, success, message = results[0]
        assert action == "high_memory"
        assert success is False
        assert message  # The OS error is surfaced


@pytest.mark.parametrize(
    ("health_kwargs", "hook", "action"),
    [
        ({"memory_percent": 95.0}, "on_high_memory", "high_memory"),
        ({"disk_percent": 95.0}, "on_high_disk", "high_disk"),
        ({"load": 10.0}, "on_high_load", "high_load"),
    ],
)
def test_each_critical_metric_triggers_its_hook(health_kwargs, hook, action):
    config = RemediationConfig(enabled=True, **{hook: "do-something"})
    handler = RemediationHandler(config, make_node())

    with mock.patch(
        "node_health_monitor.remediation.handler.subprocess.run",
        return_value=completed_process(),
    ):
        results = handler.handle(make_health(**health_kwargs))

    assert [r[0] for r in results] == [action]
