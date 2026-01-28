"""Unit tests for 'ralph serve' CLI command.

Tests the serve subcommand argument parsing and basic command structure.
Note: Full server startup is tested in integration tests.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ralph_orchestrator.cli import command_serve, build_parser


class TestServeCommandParsing:
    """Test suite for 'ralph serve' command argument parsing."""

    def test_serve_command_exists_in_parser(self):
        """Serve subcommand is registered in argument parser."""
        parser = build_parser()

        # Parse serve command to verify it exists
        args = parser.parse_args(["serve"])

        assert args.cmd == "serve"
        assert hasattr(args, "func")
        assert args.func == command_serve

    def test_serve_command_default_options(self):
        """Serve command has correct default option values."""
        parser = build_parser()
        args = parser.parse_args(["serve"])

        assert args.port == 3000
        assert args.host == "127.0.0.1"
        assert args.projects_root is None  # None means current directory
        assert args.open is False
        assert args.remote is False

    def test_serve_command_port_option(self):
        """Serve command accepts --port option."""
        parser = build_parser()

        args = parser.parse_args(["serve", "--port", "8080"])
        assert args.port == 8080

        args = parser.parse_args(["serve", "--port", "5000"])
        assert args.port == 5000

    def test_serve_command_host_option(self):
        """Serve command accepts --host option."""
        parser = build_parser()

        args = parser.parse_args(["serve", "--host", "192.168.1.100"])
        assert args.host == "192.168.1.100"

        args = parser.parse_args(["serve", "--host", "0.0.0.0"])
        assert args.host == "0.0.0.0"

    def test_serve_command_projects_root_option(self):
        """Serve command accepts --projects-root option."""
        parser = build_parser()

        args = parser.parse_args(["serve", "--projects-root", "/path/to/projects"])
        assert args.projects_root == "/path/to/projects"

    def test_serve_command_open_flag(self):
        """Serve command accepts --open flag."""
        parser = build_parser()

        args = parser.parse_args(["serve", "--open"])
        assert args.open is True

        args = parser.parse_args(["serve"])
        assert args.open is False

    def test_serve_command_remote_flag(self):
        """Serve command accepts --remote flag."""
        parser = build_parser()

        args = parser.parse_args(["serve", "--remote"])
        assert args.remote is True

        args = parser.parse_args(["serve"])
        assert args.remote is False

    def test_serve_command_combined_options(self):
        """Serve command accepts multiple options together."""
        parser = build_parser()

        args = parser.parse_args([
            "serve",
            "--port", "9000",
            "--host", "localhost",
            "--projects-root", "/home/user/projects",
            "--open",
            "--remote",
        ])

        assert args.port == 9000
        assert args.host == "localhost"
        assert args.projects_root == "/home/user/projects"
        assert args.open is True
        assert args.remote is True

    def test_serve_command_port_must_be_integer(self):
        """Port argument must be an integer."""
        parser = build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["serve", "--port", "not-a-number"])


class TestServeCommandBehavior:
    """Test suite for serve command behavior (non-server parts)."""

    def test_serve_command_nonexistent_projects_root(self, capsys):
        """Serve command returns error if projects-root doesn't exist."""
        args = argparse.Namespace(
            port=3000,
            host="127.0.0.1",
            projects_root="/nonexistent/path/that/does/not/exist",
            open=False,
            remote=False,
        )

        result = command_serve(args)

        assert result == 2
        captured = capsys.readouterr()
        assert "does not exist" in captured.err

    def test_serve_command_missing_uvicorn(self, monkeypatch, capsys):
        """Serve command returns error with helpful message if uvicorn not installed."""
        # Hide uvicorn import to simulate it not being installed
        import sys
        import builtins

        # Remove uvicorn from sys.modules if present
        if "uvicorn" in sys.modules:
            monkeypatch.delitem(sys.modules, "uvicorn")

        # Mock __import__ to raise ImportError for uvicorn
        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == "uvicorn":
                raise ImportError("No module named 'uvicorn'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        args = argparse.Namespace(
            port=3000,
            host="127.0.0.1",
            projects_root=None,
            open=False,
            remote=False,
        )

        result = command_serve(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "uvicorn is not installed" in captured.err
        assert "pip install uvicorn" in captured.err

    def test_serve_command_remote_flag_displays_warning(self, monkeypatch, capsys, tmp_path):
        """Remote flag displays security warning before starting server."""
        # Create a valid projects root
        projects_root = tmp_path / "projects"
        projects_root.mkdir()

        # Mock uvicorn.run to prevent actual server startup
        def mock_uvicorn_run(*args, **kwargs):
            # Simulate KeyboardInterrupt to exit cleanly
            raise KeyboardInterrupt()

        # Mock the uvicorn import and run
        import sys
        import types
        mock_uvicorn = types.ModuleType("uvicorn")
        mock_uvicorn.run = mock_uvicorn_run
        monkeypatch.setitem(sys.modules, "uvicorn", mock_uvicorn)

        args = argparse.Namespace(
            port=3000,
            host="127.0.0.1",
            projects_root=str(projects_root),
            open=False,
            remote=True,
        )

        # Run command - will exit via KeyboardInterrupt
        result = command_serve(args)

        # Check that warning was displayed
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "Remote access enabled" in captured.out or "remote access" in captured.out.lower()
        # Warning mentions 0.0.0.0 or shows security implications
        assert "0.0.0.0" in captured.out or "security" in captured.out.lower()

    def test_serve_command_uses_projects_root_from_args(self, monkeypatch, capsys, tmp_path):
        """Command uses projects_root from command line arguments."""
        # Create a valid projects root
        projects_root = tmp_path / "custom_projects"
        projects_root.mkdir()

        # Mock to prevent actual server startup
        def mock_uvicorn_run(*args, **kwargs):
            raise KeyboardInterrupt()

        import sys
        import types
        mock_uvicorn = types.ModuleType("uvicorn")
        mock_uvicorn.run = mock_uvicorn_run
        monkeypatch.setitem(sys.modules, "uvicorn", mock_uvicorn)

        args = argparse.Namespace(
            port=3000,
            host="127.0.0.1",
            projects_root=str(projects_root),
            open=False,
            remote=False,
        )

        command_serve(args)

        captured = capsys.readouterr()
        # Verify the projects root is mentioned in startup output
        assert str(projects_root) in captured.out

    def test_serve_command_defaults_to_current_directory(self, monkeypatch, capsys):
        """Command defaults to current directory when projects_root is None."""
        # Mock to prevent actual server startup
        def mock_uvicorn_run(*args, **kwargs):
            raise KeyboardInterrupt()

        import sys
        import types
        mock_uvicorn = types.ModuleType("uvicorn")
        mock_uvicorn.run = mock_uvicorn_run
        monkeypatch.setitem(sys.modules, "uvicorn", mock_uvicorn)

        args = argparse.Namespace(
            port=3000,
            host="127.0.0.1",
            projects_root=None,  # Should default to cwd
            open=False,
            remote=False,
        )

        command_serve(args)

        captured = capsys.readouterr()
        # Output should mention a projects root (will be cwd)
        assert "Projects root:" in captured.out or "projects root:" in captured.out.lower()


class TestServeCommandOutput:
    """Test suite for serve command output formatting."""

    def test_serve_displays_server_url(self, monkeypatch, capsys):
        """Startup output displays server URL."""
        # Mock to prevent actual server startup
        def mock_uvicorn_run(*args, **kwargs):
            raise KeyboardInterrupt()

        import sys
        import types
        mock_uvicorn = types.ModuleType("uvicorn")
        mock_uvicorn.run = mock_uvicorn_run
        monkeypatch.setitem(sys.modules, "uvicorn", mock_uvicorn)

        args = argparse.Namespace(
            port=8888,
            host="127.0.0.1",
            projects_root=None,
            open=False,
            remote=False,
        )

        command_serve(args)

        captured = capsys.readouterr()
        # Should display the URL with the specified port
        assert "http://localhost:8888" in captured.out or "http://127.0.0.1:8888" in captured.out

    def test_serve_displays_api_docs_url(self, monkeypatch, capsys):
        """Startup output displays API documentation URL."""
        # Mock to prevent actual server startup
        def mock_uvicorn_run(*args, **kwargs):
            raise KeyboardInterrupt()

        import sys
        import types
        mock_uvicorn = types.ModuleType("uvicorn")
        mock_uvicorn.run = mock_uvicorn_run
        monkeypatch.setitem(sys.modules, "uvicorn", mock_uvicorn)

        args = argparse.Namespace(
            port=3000,
            host="127.0.0.1",
            projects_root=None,
            open=False,
            remote=False,
        )

        command_serve(args)

        captured = capsys.readouterr()
        # Should display API docs URL
        assert "/docs" in captured.out

    def test_serve_displays_startup_banner(self, monkeypatch, capsys):
        """Startup output displays formatted banner."""
        # Mock to prevent actual server startup
        def mock_uvicorn_run(*args, **kwargs):
            raise KeyboardInterrupt()

        import sys
        import types
        mock_uvicorn = types.ModuleType("uvicorn")
        mock_uvicorn.run = mock_uvicorn_run
        monkeypatch.setitem(sys.modules, "uvicorn", mock_uvicorn)

        args = argparse.Namespace(
            port=3000,
            host="127.0.0.1",
            projects_root=None,
            open=False,
            remote=False,
        )

        command_serve(args)

        captured = capsys.readouterr()
        # Should have a banner/title
        assert "Ralph Orchestrator" in captured.out or "Ralph" in captured.out
        assert "Web UI" in captured.out or "Server" in captured.out


class TestServeCommandHelp:
    """Test suite for serve command help text."""

    def test_serve_command_help_includes_options(self, capsys):
        """Help text includes all command options."""
        parser = build_parser()

        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(["serve", "--help"])

        # argparse exits with 0 on --help
        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        # Verify basic command structure is present
        assert "ralph serve" in captured.out
        assert "options:" in captured.out

    def test_serve_command_help_includes_all_options(self, capsys):
        """Help text documents all command options."""
        parser = build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["serve", "--help"])

        captured = capsys.readouterr()
        help_text = captured.out

        # Verify all options are documented
        assert "--port" in help_text
        assert "--host" in help_text
        assert "--projects-root" in help_text
        assert "--open" in help_text
        assert "--remote" in help_text

        # Verify defaults are documented
        assert "3000" in help_text
        assert "127.0.0.1" in help_text

    def test_serve_command_help_mentions_security_warning(self, capsys):
        """Help text mentions security implications of --remote."""
        parser = build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["serve", "--help"])

        captured = capsys.readouterr()
        help_text = captured.out

        # Check that remote flag has security warning in help
        assert "remote" in help_text.lower()
        assert "WARNING" in help_text or "0.0.0.0" in help_text
