"""Unit tests for ralph_orchestrator/schedule.py."""

from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ralph_orchestrator.schedule import (
    SCHEDULE_MAPPINGS,
    ScheduleConfig,
    generate_launchd_plist,
    generate_systemd_service,
    generate_systemd_timer,
    get_cron_expression,
    get_launchd_path,
    get_schedule_status,
    get_systemd_service_path,
    get_systemd_timer_path,
    install_schedule,
    parse_schedule_time,
    uninstall_schedule,
    create_schedule_config_from_ralph_config,
)


class TestParseScheduleTime:
    """Tests for parse_schedule_time function."""

    def test_valid_time_morning(self):
        hour, minute = parse_schedule_time("02:00")
        assert hour == 2
        assert minute == 0

    def test_valid_time_afternoon(self):
        hour, minute = parse_schedule_time("14:30")
        assert hour == 14
        assert minute == 30

    def test_valid_time_midnight(self):
        hour, minute = parse_schedule_time("00:00")
        assert hour == 0
        assert minute == 0

    def test_valid_time_end_of_day(self):
        hour, minute = parse_schedule_time("23:59")
        assert hour == 23
        assert minute == 59

    def test_invalid_no_colon(self):
        with pytest.raises(ValueError, match="Invalid time format"):
            parse_schedule_time("0200")

    def test_invalid_hour_out_of_range(self):
        with pytest.raises(ValueError, match="Hour must be 0-23"):
            parse_schedule_time("24:00")

    def test_invalid_minute_out_of_range(self):
        with pytest.raises(ValueError, match="Minute must be 0-59"):
            parse_schedule_time("12:60")

    def test_invalid_empty_string(self):
        with pytest.raises(ValueError, match="Invalid time format"):
            parse_schedule_time("")

    def test_invalid_non_numeric(self):
        with pytest.raises(ValueError, match="Invalid time format"):
            parse_schedule_time("ab:cd")


class TestScheduleConfig:
    """Tests for ScheduleConfig dataclass."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> ScheduleConfig:
        return ScheduleConfig(
            schedule="daily",
            schedule_time="02:30",
            project_path=tmp_path / "my-project",
            project_name="my-project",
        )

    def test_hour_extraction(self, config: ScheduleConfig):
        assert config.hour == 2

    def test_minute_extraction(self, config: ScheduleConfig):
        assert config.minute == 30

    def test_second_hour_calculation(self, config: ScheduleConfig):
        # 02:30 + 12h = 14:30
        assert config.second_hour == 14

    def test_second_hour_wraparound(self, tmp_path: Path):
        config = ScheduleConfig(
            schedule="twice-daily",
            schedule_time="14:00",
            project_path=tmp_path,
            project_name="test",
        )
        # 14:00 + 12h = 02:00 (next day wrapped)
        assert config.second_hour == 2

    def test_service_id_generation(self, config: ScheduleConfig):
        service_id = config.service_id
        assert service_id.startswith("ralph-autopilot-my-project-")
        assert len(service_id) > len("ralph-autopilot-my-project-")

    def test_service_id_sanitization(self, tmp_path: Path):
        config = ScheduleConfig(
            schedule="daily",
            schedule_time="02:00",
            project_path=tmp_path,
            project_name="My Project_Name",
        )
        # Should be lowercase and dashes
        assert "my-project-name" in config.service_id
        assert "_" not in config.service_id
        assert "My" not in config.service_id


class TestGetCronExpression:
    """Tests for get_cron_expression function."""

    @pytest.fixture
    def base_config(self, tmp_path: Path) -> ScheduleConfig:
        return ScheduleConfig(
            schedule="daily",
            schedule_time="02:30",
            project_path=tmp_path,
            project_name="test",
        )

    def test_hourly(self, base_config: ScheduleConfig):
        base_config.schedule = "hourly"
        cron = get_cron_expression(base_config)
        assert cron == "0 * * * *"

    def test_daily(self, base_config: ScheduleConfig):
        base_config.schedule = "daily"
        cron = get_cron_expression(base_config)
        assert cron == "0 2 * * *"

    def test_weekly(self, base_config: ScheduleConfig):
        base_config.schedule = "weekly"
        cron = get_cron_expression(base_config)
        assert cron == "0 2 * * 0"

    def test_weekdays(self, base_config: ScheduleConfig):
        base_config.schedule = "weekdays"
        cron = get_cron_expression(base_config)
        assert cron == "0 2 * * 1-5"

    def test_twice_daily(self, base_config: ScheduleConfig):
        base_config.schedule = "twice-daily"
        cron = get_cron_expression(base_config)
        assert cron == "0 2,14 * * *"

    def test_unknown_schedule(self, base_config: ScheduleConfig):
        base_config.schedule = "invalid"
        with pytest.raises(ValueError, match="Unknown schedule"):
            get_cron_expression(base_config)


class TestGenerateLaunchdPlist:
    """Tests for generate_launchd_plist function."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> ScheduleConfig:
        return ScheduleConfig(
            schedule="daily",
            schedule_time="02:30",
            project_path=tmp_path / "my-project",
            project_name="my-project",
        )

    def test_plist_is_valid_xml(self, config: ScheduleConfig):
        plist = generate_launchd_plist(config)
        assert '<?xml version="1.0"' in plist
        assert "<!DOCTYPE plist" in plist
        assert "<plist version=" in plist

    def test_plist_contains_label(self, config: ScheduleConfig):
        plist = generate_launchd_plist(config)
        assert "<key>Label</key>" in plist
        assert f"com.ralph.{config.service_id}" in plist

    def test_plist_contains_program_arguments(self, config: ScheduleConfig):
        plist = generate_launchd_plist(config)
        assert "<key>ProgramArguments</key>" in plist
        assert "<string>autopilot</string>" in plist

    def test_plist_contains_working_directory(self, config: ScheduleConfig):
        plist = generate_launchd_plist(config)
        assert "<key>WorkingDirectory</key>" in plist
        assert str(config.project_path) in plist

    def test_plist_contains_calendar_interval(self, config: ScheduleConfig):
        plist = generate_launchd_plist(config)
        assert "<key>StartCalendarInterval</key>" in plist
        assert "<key>Hour</key>" in plist
        assert "<integer>2</integer>" in plist

    def test_plist_twice_daily_has_two_intervals(self, config: ScheduleConfig):
        config.schedule = "twice-daily"
        plist = generate_launchd_plist(config)
        # Should have two Hour entries
        assert plist.count("<key>Hour</key>") == 2

    def test_plist_weekdays_has_five_intervals(self, config: ScheduleConfig):
        config.schedule = "weekdays"
        plist = generate_launchd_plist(config)
        # Should have 5 weekday intervals
        assert plist.count("<key>Weekday</key>") == 5


class TestGenerateSystemdService:
    """Tests for generate_systemd_service function."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> ScheduleConfig:
        return ScheduleConfig(
            schedule="daily",
            schedule_time="02:30",
            project_path=tmp_path / "my-project",
            project_name="my-project",
        )

    def test_service_contains_unit_section(self, config: ScheduleConfig):
        service = generate_systemd_service(config)
        assert "[Unit]" in service
        assert "Description=Ralph Autopilot" in service

    def test_service_contains_service_section(self, config: ScheduleConfig):
        service = generate_systemd_service(config)
        assert "[Service]" in service
        assert "Type=oneshot" in service
        assert f"WorkingDirectory={config.project_path}" in service

    def test_service_contains_exec_start(self, config: ScheduleConfig):
        service = generate_systemd_service(config)
        assert "ExecStart=" in service
        assert "autopilot" in service

    def test_service_contains_install_section(self, config: ScheduleConfig):
        service = generate_systemd_service(config)
        assert "[Install]" in service


class TestGenerateSystemdTimer:
    """Tests for generate_systemd_timer function."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> ScheduleConfig:
        return ScheduleConfig(
            schedule="daily",
            schedule_time="02:30",
            project_path=tmp_path / "my-project",
            project_name="my-project",
        )

    def test_timer_contains_unit_section(self, config: ScheduleConfig):
        timer = generate_systemd_timer(config)
        assert "[Unit]" in timer
        assert "Description=" in timer

    def test_timer_contains_timer_section(self, config: ScheduleConfig):
        timer = generate_systemd_timer(config)
        assert "[Timer]" in timer
        assert "OnCalendar=" in timer
        assert "Persistent=true" in timer

    def test_timer_daily_calendar(self, config: ScheduleConfig):
        timer = generate_systemd_timer(config)
        assert "*-*-* 02:30:00" in timer

    def test_timer_weekly_calendar(self, config: ScheduleConfig):
        config.schedule = "weekly"
        timer = generate_systemd_timer(config)
        assert "Sun *-*-* 02:30:00" in timer

    def test_timer_weekdays_calendar(self, config: ScheduleConfig):
        config.schedule = "weekdays"
        timer = generate_systemd_timer(config)
        assert "Mon..Fri *-*-* 02:30:00" in timer

    def test_timer_twice_daily_calendar(self, config: ScheduleConfig):
        config.schedule = "twice-daily"
        timer = generate_systemd_timer(config)
        assert "*-*-* 02,14:30:00" in timer

    def test_timer_contains_install_section(self, config: ScheduleConfig):
        timer = generate_systemd_timer(config)
        assert "[Install]" in timer
        assert "WantedBy=timers.target" in timer


class TestGetPaths:
    """Tests for path generation functions."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> ScheduleConfig:
        return ScheduleConfig(
            schedule="daily",
            schedule_time="02:00",
            project_path=tmp_path,
            project_name="test",
        )

    def test_launchd_path(self, config: ScheduleConfig):
        path = get_launchd_path(config)
        assert path.parent == Path.home() / "Library" / "LaunchAgents"
        assert path.suffix == ".plist"
        assert config.service_id in path.name

    def test_systemd_service_path(self, config: ScheduleConfig):
        path = get_systemd_service_path(config)
        assert path.parent == Path.home() / ".config" / "systemd" / "user"
        assert path.suffix == ".service"
        assert config.service_id in path.name

    def test_systemd_timer_path(self, config: ScheduleConfig):
        path = get_systemd_timer_path(config)
        assert path.parent == Path.home() / ".config" / "systemd" / "user"
        assert path.suffix == ".timer"
        assert config.service_id in path.name


class TestInstallSchedule:
    """Tests for install_schedule function."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> ScheduleConfig:
        project_path = tmp_path / "my-project"
        project_path.mkdir(parents=True)
        return ScheduleConfig(
            schedule="daily",
            schedule_time="02:00",
            project_path=project_path,
            project_name="my-project",
        )

    @patch("ralph_orchestrator.schedule.platform.system")
    @patch("ralph_orchestrator.schedule.subprocess.run")
    def test_install_darwin_success(
        self,
        mock_run: MagicMock,
        mock_system: MagicMock,
        config: ScheduleConfig,
        tmp_path: Path,
    ):
        mock_system.return_value = "Darwin"
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        # Override path to use tmp_path
        with patch("ralph_orchestrator.schedule.get_launchd_path") as mock_path:
            plist_path = tmp_path / "test.plist"
            mock_path.return_value = plist_path

            result = install_schedule(config)

            assert result.success
            assert result.platform == "darwin"
            assert "launchd" in result.message.lower()

    @patch("ralph_orchestrator.schedule.platform.system")
    @patch("ralph_orchestrator.schedule.subprocess.run")
    def test_install_linux_success(
        self,
        mock_run: MagicMock,
        mock_system: MagicMock,
        config: ScheduleConfig,
        tmp_path: Path,
    ):
        mock_system.return_value = "Linux"
        mock_run.return_value = MagicMock(returncode=0)

        # Override paths to use tmp_path
        with patch("ralph_orchestrator.schedule.get_systemd_service_path") as mock_svc, \
             patch("ralph_orchestrator.schedule.get_systemd_timer_path") as mock_timer:
            mock_svc.return_value = tmp_path / "test.service"
            mock_timer.return_value = tmp_path / "test.timer"

            result = install_schedule(config)

            assert result.success
            assert result.platform == "linux"
            assert "systemd" in result.message.lower()

    @patch("ralph_orchestrator.schedule.platform.system")
    def test_install_unsupported_platform(
        self,
        mock_system: MagicMock,
        config: ScheduleConfig,
    ):
        mock_system.return_value = "Windows"

        result = install_schedule(config)

        assert not result.success
        assert "unsupported" in result.message.lower()


class TestUninstallSchedule:
    """Tests for uninstall_schedule function."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> ScheduleConfig:
        return ScheduleConfig(
            schedule="daily",
            schedule_time="02:00",
            project_path=tmp_path,
            project_name="test",
        )

    @patch("ralph_orchestrator.schedule.platform.system")
    @patch("ralph_orchestrator.schedule.subprocess.run")
    def test_uninstall_darwin_with_existing_plist(
        self,
        mock_run: MagicMock,
        mock_system: MagicMock,
        config: ScheduleConfig,
        tmp_path: Path,
    ):
        mock_system.return_value = "Darwin"
        mock_run.return_value = MagicMock(returncode=0)

        # Create a plist file
        plist_path = tmp_path / "test.plist"
        plist_path.write_text("test")

        with patch("ralph_orchestrator.schedule.get_launchd_path") as mock_path:
            mock_path.return_value = plist_path

            result = uninstall_schedule(config)

            assert result.success
            assert not plist_path.exists()
            assert len(result.files_removed) == 1

    @patch("ralph_orchestrator.schedule.platform.system")
    def test_uninstall_darwin_no_existing_plist(
        self,
        mock_system: MagicMock,
        config: ScheduleConfig,
        tmp_path: Path,
    ):
        mock_system.return_value = "Darwin"

        with patch("ralph_orchestrator.schedule.get_launchd_path") as mock_path:
            mock_path.return_value = tmp_path / "nonexistent.plist"

            result = uninstall_schedule(config)

            assert result.success
            assert "no launchd agent found" in result.message.lower()
            assert len(result.files_removed) == 0


class TestGetScheduleStatus:
    """Tests for get_schedule_status function."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> ScheduleConfig:
        return ScheduleConfig(
            schedule="daily",
            schedule_time="02:00",
            project_path=tmp_path,
            project_name="test",
        )

    @patch("ralph_orchestrator.schedule.platform.system")
    def test_status_darwin_not_installed(
        self,
        mock_system: MagicMock,
        config: ScheduleConfig,
        tmp_path: Path,
    ):
        mock_system.return_value = "Darwin"

        with patch("ralph_orchestrator.schedule.get_launchd_path") as mock_path:
            mock_path.return_value = tmp_path / "nonexistent.plist"

            status = get_schedule_status(config)

            assert not status.installed
            assert not status.running
            assert status.platform == "darwin"

    @patch("ralph_orchestrator.schedule.platform.system")
    @patch("ralph_orchestrator.schedule.subprocess.run")
    def test_status_darwin_installed(
        self,
        mock_run: MagicMock,
        mock_system: MagicMock,
        config: ScheduleConfig,
        tmp_path: Path,
    ):
        mock_system.return_value = "Darwin"

        # Create plist file
        plist_path = tmp_path / "test.plist"
        plist_path.write_text("test")

        # Mock launchctl list output
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=f"com.ralph.{config.service_id}\n",
        )

        with patch("ralph_orchestrator.schedule.get_launchd_path") as mock_path:
            mock_path.return_value = plist_path

            status = get_schedule_status(config)

            assert status.installed
            assert status.running
            assert plist_path in status.files


class TestCreateScheduleConfigFromRalphConfig:
    """Tests for create_schedule_config_from_ralph_config function."""

    def test_returns_none_when_no_schedule(self):
        mock_config = MagicMock()
        mock_config.autopilot.schedule = None

        result = create_schedule_config_from_ralph_config(mock_config)

        assert result is None

    def test_creates_config_with_schedule(self, tmp_path: Path):
        mock_config = MagicMock()
        mock_config.autopilot.schedule = "daily"
        mock_config.autopilot.schedule_time = "03:00"
        mock_config.repo_root = tmp_path

        result = create_schedule_config_from_ralph_config(mock_config)

        assert result is not None
        assert result.schedule == "daily"
        assert result.schedule_time == "03:00"
        assert result.project_path == tmp_path.resolve()
        assert result.project_name == tmp_path.name

    def test_uses_override_project_path(self, tmp_path: Path):
        mock_config = MagicMock()
        mock_config.autopilot.schedule = "weekly"
        mock_config.autopilot.schedule_time = "04:00"
        mock_config.repo_root = tmp_path / "default"

        override_path = tmp_path / "override"
        override_path.mkdir(parents=True)

        result = create_schedule_config_from_ralph_config(
            mock_config,
            project_path=override_path,
        )

        assert result is not None
        assert result.project_path == override_path.resolve()


class TestScheduleMappings:
    """Tests for SCHEDULE_MAPPINGS constant."""

    def test_all_schedules_have_cron(self):
        for schedule, mapping in SCHEDULE_MAPPINGS.items():
            assert "cron" in mapping, f"{schedule} missing cron"

    def test_all_schedules_have_launchd(self):
        for schedule, mapping in SCHEDULE_MAPPINGS.items():
            assert "launchd" in mapping, f"{schedule} missing launchd"

    def test_all_schedules_have_systemd_calendar(self):
        for schedule, mapping in SCHEDULE_MAPPINGS.items():
            assert "systemd_calendar" in mapping, f"{schedule} missing systemd_calendar"

    def test_all_schedules_have_description(self):
        for schedule, mapping in SCHEDULE_MAPPINGS.items():
            assert "description" in mapping, f"{schedule} missing description"

    def test_expected_schedules_exist(self):
        expected = ["hourly", "daily", "weekly", "weekdays", "twice-daily"]
        for schedule in expected:
            assert schedule in SCHEDULE_MAPPINGS
