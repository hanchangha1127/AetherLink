#!/usr/bin/env python3

import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from typing import Optional


ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "script" / "no_adb_external_relay_pairing_smoke.sh"
SUPERVISOR = ROOT / "script" / "owned_process_supervisor.sh"
NO_DEVICE_GATE = ROOT / "script" / "check_no_device_quality.sh"


def process_identity(pid: int) -> Optional[str]:
    result = subprocess.run(
        ["ps", "-ww", "-o", "lstart=", "-o", "command=", "-p", str(pid)],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    )
    identity = result.stdout.strip()
    return identity or None


def process_parent_pid(pid: int) -> Optional[int]:
    result = subprocess.run(
        ["ps", "-o", "ppid=", "-p", str(pid)],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    )
    value = result.stdout.strip()
    return int(value) if value.isdigit() else None


def wait_for_process_command(
    pid: int,
    command_fragment: str,
    timeout: float = 5.0,
) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        identity = process_identity(pid)
        if identity is not None and command_fragment in identity:
            return identity
        time.sleep(0.02)
    raise AssertionError(
        f"Timed out waiting for process {pid} command containing {command_fragment!r}"
    )


def wait_for_file(path: pathlib.Path, timeout: float = 5.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            value = ""
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError(f"Timed out waiting for {path}")


def wait_for_original_process_exit(
    pid: int,
    identity: str,
    timeout: float = 5.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process_identity(pid) != identity:
            return
        time.sleep(0.02)
    raise AssertionError(f"Original process {pid} remained alive: {identity}")


def terminate_if_same_process(pid: int, identity: Optional[str]) -> None:
    if identity is None or process_identity(pid) != identity:
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


class NoAdbExternalRelayPairingSmokeTest(unittest.TestCase):
    def test_shell_syntax(self) -> None:
        for script in (SCRIPT, SUPERVISOR):
            with self.subTest(script=script.name):
                result = subprocess.run(
                    ["bash", "-n", str(script)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_local_relay_keeps_allocation_guards_under_supervisor(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"$ROOT_DIR/script/owned_process_supervisor.sh"', source)
        self.assertIn('--owner-pid "$$"', source)
        self.assertIn('--pid-file "$RELAY_PID_FILE"', source)
        self.assertIn("--require-allocation", source)
        self.assertIn('--allocation-store "$WORK_DIR/relay-allocations.json"', source)

    def test_default_gate_supervises_every_durable_direct_relay(self) -> None:
        source = NO_DEVICE_GATE.read_text(encoding="utf-8")
        self.assertIn("trap cleanup_no_device_gate EXIT", source)
        self.assertIn("cleanup_owned_process_supervisors", source)
        for function_name in (
            "check_relay_preflight_allocation_guard",
            "check_relay_allocation_token_authorization_guard",
            "check_relay_exposed_bind_token_guard",
        ):
            start = source.index(f"{function_name}() {{")
            end = source.index("\n}\n", start)
            function = source[start:end]
            self.assertIn("start_owned_process_supervisor", function, function_name)
            self.assertIn("stop_owned_process_supervisor", function, function_name)
            self.assertIn("--allocation-store", function, function_name)

    def test_gate_durable_relay_launches_use_active_supervisor_cleanup(self) -> None:
        source = NO_DEVICE_GATE.read_text(encoding="utf-8")
        self.assertEqual(source.count("start_owned_process_supervisor \\\n    relay_supervisor_pid relay_pid"), 3)
        self.assertIn("ACTIVE_OWNED_PROCESS_SUPERVISOR_PIDS=()", source)
        self.assertIn("ACTIVE_OWNED_PROCESS_CHILD_START_TIMES=()", source)
        self.assertIn("terminate_owned_process_child_if_identical", source)
        self.assertIn("cleanup_owned_process_supervisors", source)
        self.assertIn("trap cleanup_no_device_gate EXIT", source)

    def test_supervisor_and_parent_cleanup_waits_are_bounded(self) -> None:
        supervisor_source = SUPERVISOR.read_text(encoding="utf-8")
        terminate_start = supervisor_source.index("terminate_child() {")
        terminate_end = supervisor_source.index("\n}\n", terminate_start)
        terminate_function = supervisor_source[terminate_start:terminate_end]
        self.assertIn("local kill_remaining_checks=40", terminate_function)
        self.assertIn("&& ((kill_remaining_checks > 0))", terminate_function)
        self.assertNotIn(
            "while child_is_owned_and_running; do",
            terminate_function,
        )

        for script, helper_name, matcher in (
            (
                NO_DEVICE_GATE,
                "stop_and_reap_owned_process_supervisor_if_identical",
                "owned_process_matches_identity",
            ),
            (
                SCRIPT,
                "stop_and_reap_relay_supervisor_if_identical",
                "relay_process_matches_identity",
            ),
        ):
            source = script.read_text(encoding="utf-8")
            helper_start = source.index(f"{helper_name}() {{")
            helper_end = source.index("\n}\n", helper_start)
            helper = source[helper_start:helper_end]
            self.assertIn("local term_remaining_checks=60", helper)
            self.assertIn("local kill_remaining_checks=40", helper)
            self.assertIn("kill -KILL", helper)
            self.assertIn(f"if ! {matcher}", helper)
            self.assertIn('wait "$supervisor_pid"', helper)

            cleanup_start = source.index(
                "stop_owned_process_supervisor() {"
                if script == NO_DEVICE_GATE
                else "cleanup_recorded_relay_process() {"
            )
            cleanup_end = source.index("\n}\n", cleanup_start)
            cleanup = source[cleanup_start:cleanup_end]
            self.assertNotIn('\n  wait "$supervisor_pid"', cleanup)

    def run_parent_cleanup_self_test(
        self,
        script: pathlib.Path,
        expected_output: str,
    ) -> None:
        environment = os.environ.copy()
        environment["AETHERLINK_OWNED_PROCESS_CLEANUP_SELF_TEST"] = "1"
        result = subprocess.run(
            ["bash", str(script)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(expected_output, result.stdout)

    def test_default_gate_parent_cleanup_recovers_child_after_supervisor_sigkill(
        self,
    ) -> None:
        self.run_parent_cleanup_self_test(
            NO_DEVICE_GATE,
            "Default gate owned-process cleanup self-test passed.",
        )

    def test_no_adb_parent_cleanup_recovers_child_after_supervisor_sigkill(
        self,
    ) -> None:
        self.run_parent_cleanup_self_test(
            SCRIPT,
            "No-ADB owned-process cleanup self-test passed.",
        )

    def test_supervisor_rejects_non_parent_owner_before_starting_child(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-relay-supervisor-owner-reject-"
        ) as work_dir:
            work_path = pathlib.Path(work_dir)
            marker_path = work_path / "started.txt"
            result = subprocess.run(
                [
                    "bash",
                    str(SUPERVISOR),
                    "--owner-pid",
                    str(os.getpid() + 1),
                    "--pid-file",
                    str(work_path / "child.pid"),
                    "--",
                    sys.executable,
                    "-c",
                    "import pathlib, sys; pathlib.Path(sys.argv[1]).touch()",
                    str(marker_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("direct parent", result.stderr)
            self.assertFalse(marker_path.exists())

    def test_supervisor_forwards_shutdown_signals_without_sockets(self) -> None:
        fake_child = """
import os
import pathlib
import signal
import sys
import time

marker = pathlib.Path(sys.argv[1])

def stop(signum, _frame):
    marker.write_text(f"{signum}\\n", encoding="utf-8")
    raise SystemExit(0)

for name in ("SIGTERM", "SIGINT", "SIGHUP"):
    signal.signal(getattr(signal, name), stop)
pathlib.Path(sys.argv[2]).write_text(f"{os.getpid()}\\n", encoding="utf-8")
while True:
    time.sleep(30)
"""
        for forwarded_signal in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            with self.subTest(signal=forwarded_signal):
                with tempfile.TemporaryDirectory(
                    prefix="aetherlink-relay-supervisor-signal-"
                ) as work_dir:
                    work_path = pathlib.Path(work_dir)
                    marker_path = work_path / "signal.txt"
                    ready_path = work_path / "ready.pid"
                    child_pid_path = work_path / "child.pid"
                    supervisor = subprocess.Popen(
                        [
                            "bash",
                            str(SUPERVISOR),
                            "--owner-pid",
                            str(os.getpid()),
                            "--pid-file",
                            str(child_pid_path),
                            "--grace-seconds",
                            "1",
                            "--",
                            sys.executable,
                            "-c",
                            fake_child,
                            str(marker_path),
                            str(ready_path),
                        ],
                        cwd=ROOT,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    supervisor_identity = None
                    child_pid = 0
                    child_identity = None
                    try:
                        self.assertEqual(
                            int(wait_for_file(ready_path)),
                            int(wait_for_file(child_pid_path)),
                        )
                        child_pid = int(wait_for_file(child_pid_path))
                        self.assertEqual(
                            child_pid_path.stat().st_mode & 0o777,
                            0o600,
                        )
                        supervisor_identity = process_identity(supervisor.pid)
                        child_identity = process_identity(child_pid)
                        self.assertIsNotNone(supervisor_identity)
                        self.assertIsNotNone(child_identity)

                        os.kill(supervisor.pid, forwarded_signal)
                        supervisor.wait(timeout=5)
                        self.assertEqual(
                            marker_path.read_text(encoding="utf-8").strip(),
                            str(forwarded_signal.value),
                        )
                        wait_for_original_process_exit(child_pid, child_identity)
                    finally:
                        terminate_if_same_process(child_pid, child_identity)
                        terminate_if_same_process(
                            supervisor.pid,
                            supervisor_identity,
                        )
                        try:
                            supervisor.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            pass

    def test_child_exec_restores_default_term_int_and_hup(self) -> None:
        launcher_script = """
set -euo pipefail
trap '' TERM INT HUP
supervisor="$1"
supervisor_pid_file="$2"
child_pid_file="$3"
"$supervisor" \\
  --owner-pid "$$" \\
  --pid-file "$child_pid_file" \\
  --grace-seconds 2 \\
  -- /bin/sleep 30 &
supervisor_pid="$!"
printf '%s\\n' "$supervisor_pid" >"$supervisor_pid_file"
wait "$supervisor_pid"
"""
        for reset_signal in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            with self.subTest(signal=reset_signal):
                with tempfile.TemporaryDirectory(
                    prefix="aetherlink-relay-supervisor-default-signal-"
                ) as work_dir:
                    work_path = pathlib.Path(work_dir)
                    supervisor_pid_path = work_path / "supervisor.pid"
                    child_pid_path = work_path / "child.pid"
                    launcher = subprocess.Popen(
                        [
                            "bash",
                            "-c",
                            launcher_script,
                            "launcher",
                            str(SUPERVISOR),
                            str(supervisor_pid_path),
                            str(child_pid_path),
                        ],
                        cwd=ROOT,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launcher_identity = process_identity(launcher.pid)
                    supervisor_pid = 0
                    child_pid = 0
                    supervisor_identity = None
                    child_identity = None
                    try:
                        supervisor_pid = int(wait_for_file(supervisor_pid_path))
                        child_pid = int(wait_for_file(child_pid_path))
                        supervisor_identity = process_identity(supervisor_pid)
                        child_identity = wait_for_process_command(child_pid, "/bin/sleep 30")
                        self.assertIsNotNone(supervisor_identity)
                        self.assertIsNotNone(child_identity)
                        self.assertEqual(process_parent_pid(child_pid), supervisor_pid)

                        signal_started_at = time.monotonic()
                        os.kill(child_pid, reset_signal)
                        wait_for_original_process_exit(child_pid, child_identity)
                        launcher.wait(timeout=5)
                        self.assertLess(time.monotonic() - signal_started_at, 1.5)
                    finally:
                        terminate_if_same_process(child_pid, child_identity)
                        terminate_if_same_process(supervisor_pid, supervisor_identity)
                        terminate_if_same_process(launcher.pid, launcher_identity)
                        try:
                            launcher.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            pass

    def test_owner_sigkill_terminates_supervisor_and_child_without_sockets(self) -> None:
        ignoring_child = """
import os
import pathlib
import signal
import sys
import time

marker = pathlib.Path(sys.argv[1])

def observe(signum, _frame):
    marker.write_text(f"{signum}\\n", encoding="utf-8")

for name in ("SIGTERM", "SIGINT", "SIGHUP"):
    signal.signal(getattr(signal, name), observe)
pathlib.Path(sys.argv[2]).write_text(f"{os.getpid()}\\n", encoding="utf-8")
while True:
    time.sleep(30)
"""
        launcher_script = """
set -euo pipefail
supervisor="$1"
supervisor_pid_file="$2"
child_pid_file="$3"
marker_file="$4"
ready_file="$5"
python="$6"
child_source="$7"
"$supervisor" \\
  --owner-pid "$$" \\
  --pid-file "$child_pid_file" \\
  --grace-seconds 1 \\
  -- "$python" -c "$child_source" "$marker_file" "$ready_file" &
supervisor_pid="$!"
printf '%s\\n' "$supervisor_pid" >"$supervisor_pid_file"
wait "$supervisor_pid"
"""
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-relay-supervisor-owner-"
        ) as work_dir:
            work_path = pathlib.Path(work_dir)
            supervisor_pid_path = work_path / "supervisor.pid"
            child_pid_path = work_path / "child.pid"
            marker_path = work_path / "signal.txt"
            ready_path = work_path / "ready.pid"
            launcher = subprocess.Popen(
                [
                    "bash",
                    "-c",
                    launcher_script,
                    "launcher",
                    str(SUPERVISOR),
                    str(supervisor_pid_path),
                    str(child_pid_path),
                    str(marker_path),
                    str(ready_path),
                    sys.executable,
                    ignoring_child,
                ],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            launcher_identity = process_identity(launcher.pid)
            supervisor_pid = 0
            child_pid = 0
            supervisor_identity = None
            child_identity = None
            try:
                supervisor_pid = int(wait_for_file(supervisor_pid_path))
                child_pid = int(wait_for_file(child_pid_path))
                self.assertEqual(int(wait_for_file(ready_path)), child_pid)

                supervisor_identity = process_identity(supervisor_pid)
                child_identity = process_identity(child_pid)
                self.assertIsNotNone(launcher_identity)
                self.assertIsNotNone(supervisor_identity)
                self.assertIsNotNone(child_identity)
                self.assertEqual(process_parent_pid(supervisor_pid), launcher.pid)
                self.assertEqual(process_parent_pid(child_pid), supervisor_pid)

                owner_killed_at = time.monotonic()
                os.kill(launcher.pid, signal.SIGKILL)
                launcher.wait(timeout=2)
                wait_for_original_process_exit(
                    supervisor_pid,
                    supervisor_identity,
                    timeout=5,
                )
                wait_for_original_process_exit(
                    child_pid,
                    child_identity,
                    timeout=5,
                )
                elapsed = time.monotonic() - owner_killed_at
                self.assertEqual(wait_for_file(marker_path), str(signal.SIGTERM.value))
                self.assertGreaterEqual(elapsed, 0.75)
                self.assertLess(elapsed, 5.0)
            finally:
                terminate_if_same_process(child_pid, child_identity)
                terminate_if_same_process(supervisor_pid, supervisor_identity)
                terminate_if_same_process(launcher.pid, launcher_identity)
                try:
                    launcher.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass

    def test_correlated_evidence_self_test_fails_closed_without_network(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aetherlink-evidence-self-test-") as work_dir:
            result = subprocess.run(
                [
                    "bash",
                    str(SCRIPT),
                    "--self-test-evidence-correlation",
                    "--work-dir",
                    work_dir,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout.strip(),
                "Correlated evidence no-network self-test passed.",
            )
            combined_output = result.stdout + result.stderr
            for secret_label in (
                "pairing_nonce=",
                "pairing_code=",
                "relay_id=",
                "relay_secret=",
                "relay_nonce=",
                "route_token=",
            ):
                self.assertNotIn(secret_label, combined_output)

            with open(
                pathlib.Path(work_dir) / "evidence-state.json",
                encoding="utf-8",
            ) as handle:
                state = json.load(handle)

            self.assertEqual(
                state,
                {
                    "correlation_valid": True,
                    "failure_reason": None,
                    "pairing_accepted": True,
                    "reconnect_ready": True,
                    "reconnect_transition": True,
                    "relay_ready": True,
                    "route_anchor_present": True,
                    "run_anchor_present": True,
                    "runtime_health": True,
                    "runtime_health_count": 2,
                    "runtime_waiting_for_peer": True,
                    "same_run_route_session_sequence": True,
                    "trusted_device_reconnect": True,
                },
            )

            with open(
                pathlib.Path(work_dir) / "summary.json",
                encoding="utf-8",
            ) as handle:
                summary = json.load(handle)

            self.assertTrue(summary["mode"]["evidence_correlation_self_test"])
            self.assertTrue(
                summary["coverage"]["evidence_correlation_fixture_verified"]
            )
            for field in (
                "trusted_device_relay_reachability",
                "trusted_device_pairing",
                "trusted_device_runtime_health",
                "trusted_device_reconnect",
                "full_run_trusted_device_proof",
                "external_network_relay_verified",
                "production_relay",
            ):
                self.assertFalse(summary["coverage"][field], field)
            self.assertIn(
                "no_network_evidence_correlation_fixture_only",
                summary["caveats"],
            )


if __name__ == "__main__":
    unittest.main()
