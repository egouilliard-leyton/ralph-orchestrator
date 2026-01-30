"""Scheduler module for Ralph autopilot.

Generates and manages system service files (launchd on macOS, systemd on Linux)
for scheduled autopilot execution.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Schedule keyword to cron-style mapping
SCHEDULE_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "hourly": {
        "cron": "0 * * * *",
        "launchd": {"Minute": 0},
        "systemd_calendar": "*-*-* *:00:00",
        "description": "Every hour at minute 0",
    },
    "daily": {
        "cron": "0 {hour} * * *",
        "launchd": {"Hour": "{hour}", "Minute": "{minute}"},
        "systemd_calendar": "*-*-* {hour}:{minute}:00",
        "description": "Daily at {time}",
    },
    "weekly": {
        "cron": "0 {hour} * * 0",
        "launchd": {"Weekday": 0, "Hour": "{hour}", "Minute": "{minute}"},
        "systemd_calendar": "Sun *-*-* {hour}:{minute}:00",
        "description": "Weekly on Sunday at {time}",
    },
    "weekdays": {
        "cron": "0 {hour} * * 1-5",
        "launchd": {"Weekday": [1, 2, 3, 4, 5], "Hour": "{hour}", "Minute": "{minute}"},
        "systemd_calendar": "Mon..Fri *-*-* {hour}:{minute}:00",
        "description": "Weekdays (Mon-Fri) at {time}",
    },
    "twice-daily": {
        "cron": "0 {hour},{hour2} * * *",
        "launchd": {"Hour": ["{hour}", "{hour2}"], "Minute": "{minute}"},
        "systemd_calendar": "*-*-* {hour},{hour2}:{minute}:00",
        "description": "Twice daily at {time} and {time2}",
    },
}


@dataclass
class ScheduleConfig:
    """Configuration for scheduled autopilot execution."""

    schedule: str  # Keyword: hourly, daily, weekly, weekdays, twice-daily
    schedule_time: str  # Time in HH:MM format (24h)
    project_path: Path  # Absolute path to the project
    project_name: str  # Project identifier (for service naming)

    @property
    def hour(self) -> int:
        """Extract hour from schedule_time."""
        return int(self.schedule_time.split(":")[0])

    @property
    def minute(self) -> int:
        """Extract minute from schedule_time."""
        return int(self.schedule_time.split(":")[1])

    @property
    def second_hour(self) -> int:
        """Calculate second hour for twice-daily (12 hours later)."""
        return (self.hour + 12) % 24

    @property
    def service_id(self) -> str:
        """Generate unique service identifier based on project path."""
        # Use hash of project path for uniqueness
        path_hash = hashlib.md5(str(self.project_path).encode()).hexdigest()[:8]
        safe_name = self.project_name.lower().replace(" ", "-").replace("_", "-")
        return f"ralph-autopilot-{safe_name}-{path_hash}"


def parse_schedule_time(time_str: str) -> Tuple[int, int]:
    """Parse a time string in HH:MM format.

    Args:
        time_str: Time string like "02:00" or "14:30"

    Returns:
        Tuple of (hour, minute)

    Raises:
        ValueError: If time format is invalid
    """
    if not time_str or ":" not in time_str:
        raise ValueError(f"Invalid time format: {time_str} (expected HH:MM)")

    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {time_str} (expected HH:MM)")

    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as e:
        raise ValueError(f"Invalid time format: {time_str} ({e})")

    if not (0 <= hour <= 23):
        raise ValueError(f"Hour must be 0-23, got {hour}")
    if not (0 <= minute <= 59):
        raise ValueError(f"Minute must be 0-59, got {minute}")

    return hour, minute


def get_cron_expression(config: ScheduleConfig) -> str:
    """Generate cron expression for the schedule.

    Args:
        config: Schedule configuration

    Returns:
        Cron expression string (e.g., "0 2 * * *")
    """
    mapping = SCHEDULE_MAPPINGS.get(config.schedule)
    if not mapping:
        raise ValueError(f"Unknown schedule: {config.schedule}")

    cron_template = mapping["cron"]
    return cron_template.format(
        hour=config.hour,
        minute=config.minute,
        hour2=config.second_hour,
    )


def generate_launchd_plist(config: ScheduleConfig) -> str:
    """Generate macOS launchd plist XML content.

    Args:
        config: Schedule configuration

    Returns:
        XML string for the plist file
    """
    mapping = SCHEDULE_MAPPINGS.get(config.schedule)
    if not mapping:
        raise ValueError(f"Unknown schedule: {config.schedule}")

    # Build calendar interval(s)
    launchd_spec = mapping["launchd"]
    calendar_intervals = []

    def build_interval(spec: Dict[str, Any]) -> str:
        """Build a single calendar interval dict."""
        lines = ["      <dict>"]
        for key, value in spec.items():
            if isinstance(value, list):
                # Multiple values (e.g., multiple hours)
                for v in value:
                    resolved = str(v).format(hour=config.hour, minute=config.minute, hour2=config.second_hour)
                    lines.append(f"        <key>{key}</key>")
                    lines.append(f"        <integer>{resolved}</integer>")
            else:
                resolved = str(value).format(hour=config.hour, minute=config.minute, hour2=config.second_hour)
                lines.append(f"        <key>{key}</key>")
                lines.append(f"        <integer>{resolved}</integer>")
        lines.append("      </dict>")
        return "\n".join(lines)

    # Handle schedules with multiple intervals (like twice-daily with separate hours)
    if config.schedule == "twice-daily":
        # Create two separate intervals
        interval1 = {"Hour": config.hour, "Minute": config.minute}
        interval2 = {"Hour": config.second_hour, "Minute": config.minute}
        calendar_intervals.append(build_interval(interval1))
        calendar_intervals.append(build_interval(interval2))
    elif config.schedule == "weekdays":
        # Create interval for each weekday
        for weekday in [1, 2, 3, 4, 5]:
            interval = {"Weekday": weekday, "Hour": config.hour, "Minute": config.minute}
            calendar_intervals.append(build_interval(interval))
    else:
        # Single interval
        resolved_spec = {}
        for key, value in launchd_spec.items():
            if isinstance(value, str):
                resolved_spec[key] = int(str(value).format(hour=config.hour, minute=config.minute))
            else:
                resolved_spec[key] = value
        calendar_intervals.append(build_interval(resolved_spec))

    calendar_xml = "\n".join(calendar_intervals)

    # Get paths
    ralph_cmd = shutil.which("ralph") or "ralph"
    python_path = sys.executable
    log_dir = config.project_path / ".ralph" / "logs"

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ralph.{config.service_id}</string>

  <key>ProgramArguments</key>
  <array>
    <string>{ralph_cmd}</string>
    <string>autopilot</string>
  </array>

  <key>WorkingDirectory</key>
  <string>{config.project_path}</string>

  <key>StartCalendarInterval</key>
  <array>
{calendar_xml}
  </array>

  <key>StandardOutPath</key>
  <string>{log_dir}/autopilot-schedule.log</string>

  <key>StandardErrorPath</key>
  <string>{log_dir}/autopilot-schedule.err</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:{Path(python_path).parent}</string>
  </dict>

  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
"""
    return plist


def generate_systemd_service(config: ScheduleConfig) -> str:
    """Generate Linux systemd service unit content.

    Args:
        config: Schedule configuration

    Returns:
        INI-style string for the service file
    """
    ralph_cmd = shutil.which("ralph") or "ralph"
    python_path = sys.executable

    service = f"""[Unit]
Description=Ralph Autopilot for {config.project_name}
After=network.target

[Service]
Type=oneshot
WorkingDirectory={config.project_path}
ExecStart={ralph_cmd} autopilot
Environment="PATH=/usr/local/bin:/usr/bin:/bin:{Path(python_path).parent}"

[Install]
WantedBy=default.target
"""
    return service


def generate_systemd_timer(config: ScheduleConfig) -> str:
    """Generate Linux systemd timer unit content.

    Args:
        config: Schedule configuration

    Returns:
        INI-style string for the timer file
    """
    mapping = SCHEDULE_MAPPINGS.get(config.schedule)
    if not mapping:
        raise ValueError(f"Unknown schedule: {config.schedule}")

    calendar_template = mapping["systemd_calendar"]
    calendar = calendar_template.format(
        hour=f"{config.hour:02d}",
        minute=f"{config.minute:02d}",
        hour2=f"{config.second_hour:02d}",
    )

    timer = f"""[Unit]
Description=Timer for Ralph Autopilot ({config.project_name})

[Timer]
OnCalendar={calendar}
Persistent=true

[Install]
WantedBy=timers.target
"""
    return timer


def get_launchd_path(config: ScheduleConfig) -> Path:
    """Get the path for the launchd plist file."""
    return Path.home() / "Library" / "LaunchAgents" / f"com.ralph.{config.service_id}.plist"


def get_systemd_service_path(config: ScheduleConfig) -> Path:
    """Get the path for the systemd service file."""
    return Path.home() / ".config" / "systemd" / "user" / f"{config.service_id}.service"


def get_systemd_timer_path(config: ScheduleConfig) -> Path:
    """Get the path for the systemd timer file."""
    return Path.home() / ".config" / "systemd" / "user" / f"{config.service_id}.timer"


@dataclass
class InstallResult:
    """Result of schedule installation."""

    success: bool
    message: str
    files_created: List[Path]
    platform: str


def install_schedule(config: ScheduleConfig) -> InstallResult:
    """Install the schedule as a system service.

    Args:
        config: Schedule configuration

    Returns:
        InstallResult with status and created files
    """
    system = platform.system()
    files_created: List[Path] = []

    # Ensure log directory exists
    log_dir = config.project_path / ".ralph" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if system == "Darwin":
        # macOS: install launchd plist
        plist_path = get_launchd_path(config)
        plist_path.parent.mkdir(parents=True, exist_ok=True)

        plist_content = generate_launchd_plist(config)
        plist_path.write_text(plist_content, encoding="utf-8")
        files_created.append(plist_path)

        # Load the agent
        try:
            subprocess.run(
                ["launchctl", "unload", str(plist_path)],
                capture_output=True,
                check=False,
            )
            result = subprocess.run(
                ["launchctl", "load", str(plist_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return InstallResult(
                    success=False,
                    message=f"Failed to load launchd agent: {result.stderr}",
                    files_created=files_created,
                    platform="darwin",
                )
        except Exception as e:
            return InstallResult(
                success=False,
                message=f"Failed to load launchd agent: {e}",
                files_created=files_created,
                platform="darwin",
            )

        return InstallResult(
            success=True,
            message=f"Installed launchd agent: {plist_path}",
            files_created=files_created,
            platform="darwin",
        )

    elif system == "Linux":
        # Linux: install systemd service and timer
        systemd_dir = Path.home() / ".config" / "systemd" / "user"
        systemd_dir.mkdir(parents=True, exist_ok=True)

        service_path = get_systemd_service_path(config)
        timer_path = get_systemd_timer_path(config)

        service_content = generate_systemd_service(config)
        timer_content = generate_systemd_timer(config)

        service_path.write_text(service_content, encoding="utf-8")
        timer_path.write_text(timer_content, encoding="utf-8")
        files_created.extend([service_path, timer_path])

        # Reload and enable timer
        try:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            subprocess.run(
                ["systemctl", "--user", "enable", "--now", timer_path.name],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            return InstallResult(
                success=False,
                message=f"Failed to enable systemd timer: {e}",
                files_created=files_created,
                platform="linux",
            )

        return InstallResult(
            success=True,
            message=f"Installed systemd timer: {timer_path}",
            files_created=files_created,
            platform="linux",
        )

    else:
        return InstallResult(
            success=False,
            message=f"Unsupported platform: {system}. Only macOS and Linux are supported.",
            files_created=[],
            platform=system.lower(),
        )


@dataclass
class UninstallResult:
    """Result of schedule uninstallation."""

    success: bool
    message: str
    files_removed: List[Path]


def uninstall_schedule(config: ScheduleConfig) -> UninstallResult:
    """Uninstall the scheduled service.

    Args:
        config: Schedule configuration

    Returns:
        UninstallResult with status and removed files
    """
    system = platform.system()
    files_removed: List[Path] = []

    if system == "Darwin":
        plist_path = get_launchd_path(config)

        if plist_path.exists():
            # Unload the agent
            try:
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)],
                    capture_output=True,
                    check=False,
                )
            except Exception:
                pass  # Best effort

            plist_path.unlink()
            files_removed.append(plist_path)

            return UninstallResult(
                success=True,
                message=f"Removed launchd agent: {plist_path}",
                files_removed=files_removed,
            )
        else:
            return UninstallResult(
                success=True,
                message="No launchd agent found to remove",
                files_removed=[],
            )

    elif system == "Linux":
        service_path = get_systemd_service_path(config)
        timer_path = get_systemd_timer_path(config)

        # Stop and disable timer
        try:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", timer_path.name],
                capture_output=True,
                check=False,
            )
        except Exception:
            pass

        for path in [timer_path, service_path]:
            if path.exists():
                path.unlink()
                files_removed.append(path)

        if files_removed:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
            return UninstallResult(
                success=True,
                message=f"Removed systemd files: {', '.join(str(p) for p in files_removed)}",
                files_removed=files_removed,
            )
        else:
            return UninstallResult(
                success=True,
                message="No systemd files found to remove",
                files_removed=[],
            )

    else:
        return UninstallResult(
            success=False,
            message=f"Unsupported platform: {system}",
            files_removed=[],
        )


@dataclass
class ScheduleStatus:
    """Status of the installed schedule."""

    installed: bool
    running: bool
    schedule: Optional[str]
    next_run: Optional[str]
    files: List[Path]
    platform: str


def get_schedule_status(config: ScheduleConfig) -> ScheduleStatus:
    """Get the status of the installed schedule.

    Args:
        config: Schedule configuration

    Returns:
        ScheduleStatus with current state
    """
    system = platform.system()
    files: List[Path] = []
    installed = False
    running = False
    next_run: Optional[str] = None

    if system == "Darwin":
        plist_path = get_launchd_path(config)
        if plist_path.exists():
            files.append(plist_path)
            installed = True

            # Check if loaded
            try:
                result = subprocess.run(
                    ["launchctl", "list"],
                    capture_output=True,
                    text=True,
                )
                service_label = f"com.ralph.{config.service_id}"
                running = service_label in result.stdout
            except Exception:
                pass

        return ScheduleStatus(
            installed=installed,
            running=running,
            schedule=config.schedule if installed else None,
            next_run=next_run,
            files=files,
            platform="darwin",
        )

    elif system == "Linux":
        service_path = get_systemd_service_path(config)
        timer_path = get_systemd_timer_path(config)

        for path in [service_path, timer_path]:
            if path.exists():
                files.append(path)

        installed = len(files) == 2

        if installed:
            # Check timer status
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "is-active", timer_path.name],
                    capture_output=True,
                    text=True,
                )
                running = result.stdout.strip() == "active"

                # Get next run time
                result = subprocess.run(
                    ["systemctl", "--user", "list-timers", timer_path.name, "--no-pager"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) > 1:
                        # Parse next run from output
                        parts = lines[1].split()
                        if len(parts) >= 2:
                            next_run = f"{parts[0]} {parts[1]}"
            except Exception:
                pass

        return ScheduleStatus(
            installed=installed,
            running=running,
            schedule=config.schedule if installed else None,
            next_run=next_run,
            files=files,
            platform="linux",
        )

    else:
        return ScheduleStatus(
            installed=False,
            running=False,
            schedule=None,
            next_run=None,
            files=[],
            platform=system.lower(),
        )


def create_schedule_config_from_ralph_config(
    ralph_config: Any,  # RalphConfig from config.py
    project_path: Optional[Path] = None,
) -> Optional[ScheduleConfig]:
    """Create a ScheduleConfig from a RalphConfig.

    Args:
        ralph_config: The RalphConfig object
        project_path: Optional project path override

    Returns:
        ScheduleConfig if schedule is configured, None otherwise
    """
    if not ralph_config.autopilot.schedule:
        return None

    if project_path is None:
        project_path = ralph_config.repo_root

    # Derive project name from directory
    project_name = project_path.name

    return ScheduleConfig(
        schedule=ralph_config.autopilot.schedule,
        schedule_time=ralph_config.autopilot.schedule_time,
        project_path=project_path.resolve(),
        project_name=project_name,
    )
