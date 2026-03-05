"""
Docker-based bash execution sandbox.

Provides a (usually) persistent, resource-limited container for running bash
commands. This is intended for experimental agents that treat the filesystem
as external working memory (e.g. writing /agent/state.md, /agent/reasoning.md).

If Docker is unavailable or the container cannot be created, the sandbox
degrades gracefully: commands will return an error string instead of raising.
"""

from __future__ import annotations

import atexit
import re
from typing import Any, Dict, Optional

import docker
from docker.errors import DockerException


DEFAULT_SANDBOX_CONFIG: Dict[str, Any] = {
    "sandbox": {
        # Max wall-clock seconds for a single exec
        "timeout": 30,
        # Truncate stdout/stderr to this many characters
        "max_output_chars": 10_000,
        # Docker image to use for the sandbox container
        "image": "python:3.12-slim",
        # Resource limits
        "mem_limit": "512m",
        "cpu_quota": 50_000,  # 50% of a CPU (period=100_000)
        # Networking: default to fully disabled for safety
        "network": "none",
    },
    "blacklist": {
        # Simple command-prefix blacklist (exact prefix match after strip())
        "commands": [
            "docker",
            "mount",
            "umount",
            "chmod",
            "chown",
            "useradd",
            "usermod",
            "shutdown",
            "reboot",
        ],
        # Regex patterns that, if matched, will cause the command to be rejected
        "patterns": [
            r"rm\s+-rf\s+/\b",
            r":\s*\(\)\s*\{\s*:\s*\|\s*:&\s*;\s*\}",  # fork-bomb style
        ],
    },
}


class Sandbox:
    """Manages a Docker container for command execution.

    The sandbox is *best-effort*:
      - If Docker is available, we create one long-lived container per Sandbox.
      - If Docker is not available or container startup fails, `run()` returns
        an error result instead of raising.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or DEFAULT_SANDBOX_CONFIG
        sb_cfg = cfg.get("sandbox", {})

        self.timeout: int = int(sb_cfg.get("timeout", 30))
        self.max_output: int = int(sb_cfg.get("max_output_chars", 10_000))
        blacklist = cfg.get("blacklist", {}) or {}
        self.blacklist_cmds = list(blacklist.get("commands", []))
        self.blacklist_patterns = [
            re.compile(p) for p in blacklist.get("patterns", []) or []
        ]

        try:
            self.client = docker.from_env()
            self.container = self.client.containers.run(
                sb_cfg.get("image", "python:3.12-slim"),
                command="sleep infinity",
                detach=True,
                mem_limit=sb_cfg.get("mem_limit", "512m"),
                cpu_period=100_000,
                cpu_quota=sb_cfg.get("cpu_quota", 50_000),
                network_mode=sb_cfg.get("network", "none"),
                security_opt=["no-new-privileges"],
                tmpfs={"/tmp": "size=100m"},
            )
        except DockerException as e:  # pragma: no cover - environment-specific
            # Fail fast so misconfiguration is visible to the caller.
            raise RuntimeError(f"Failed to start Docker sandbox container: {e}") from e

        # Best-effort cleanup at process exit
        atexit.register(self.cleanup)

    # ── Safety check ──────────────────────────────────────────────

    def _check_blacklist(self, command: str) -> Optional[str]:
        """Return a rejection reason if the command is blacklisted, else None."""
        cmd_stripped = command.strip()

        for blocked in self.blacklist_cmds:
            if cmd_stripped.startswith(blocked):
                return f"Command blocked: matches blacklisted prefix '{blocked}'"

        for pattern in self.blacklist_patterns:
            if pattern.search(cmd_stripped):
                return f"Command blocked: matches blacklisted pattern '{pattern.pattern}'"

        return None

    # ── Execution ─────────────────────────────────────────────────

    def run(self, command: str) -> Dict[str, Any]:
        """
        Execute a bash command inside the sandbox.

        Returns:
            dict with keys: exit_code, stdout, stderr
        """
        rejection = self._check_blacklist(command)
        if rejection:
            return {"exit_code": -1, "stdout": "", "stderr": rejection}

        if not self.container:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "Sandbox unavailable: Docker is not configured or container could not be started.",
            }

        try:
            # demux=True → (stdout, stderr) as separate byte strings
            # NOTE: docker SDK exec_run does not support a timeout kwarg; rely on
            # container-level limits and higher-level orchestration timeouts.
            exit_code, output = self.container.exec_run(
                ["bash", "-c", command],
                demux=True,
            )
            stdout_bytes, stderr_bytes = output
            stdout = (stdout_bytes or b"").decode(errors="replace")
            stderr = (stderr_bytes or b"").decode(errors="replace")

            return {
                "exit_code": int(exit_code),
                "stdout": stdout[: self.max_output],
                "stderr": stderr[: self.max_output],
            }
        except Exception as e:  # pragma: no cover - defensive
            return {"exit_code": -1, "stdout": "", "stderr": f"Sandbox error: {e}"}

    # ── Lifecycle ─────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Stop and remove the container."""
        if not self.container:
            return
        try:
            try:
                self.container.stop(timeout=2)
            finally:
                self.container.remove()
        except Exception:
            # Best-effort only; avoid raising during interpreter shutdown
            pass

