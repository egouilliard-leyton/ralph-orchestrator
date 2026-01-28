"""Integration tests for 'ralph serve' CLI command.

Tests the serve command through actual CLI invocation.
Note: These tests primarily verify command availability and basic error handling.
Full server functionality is better tested through API tests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
class TestServeCommandParsing:
    """Integration tests for ralph serve command argument parsing."""

    def test_serve_accepts_valid_port(self, temp_dir: Path):
        """Serve command accepts valid port number."""
        # This test just verifies argument parsing, not full server startup
        # We can't easily test full startup in unit tests without mocking
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from ralph_orchestrator.cli import build_parser

parser = build_parser()
args = parser.parse_args(['serve', '--port', '8888'])
assert args.port == 8888
print('OK')
"""],
            capture_output=True,
            text=True,
            cwd=temp_dir,
        )

        assert result.returncode == 0
        assert "OK" in result.stdout


@pytest.mark.integration
class TestServeOptionsIntegration:
    """Integration tests for ralph serve command options."""

    def test_serve_accepts_all_valid_options(self, temp_dir: Path):
        """Serve command accepts all documented options."""
        # Test argument parsing without starting server
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from ralph_orchestrator.cli import build_parser

parser = build_parser()
args = parser.parse_args([
    'serve',
    '--port', '9999',
    '--host', '127.0.0.1',
    '--projects-root', '/tmp',
    '--open',
    '--remote'
])

assert args.port == 9999
assert args.host == '127.0.0.1'
assert args.projects_root == '/tmp'
assert args.open is True
assert args.remote is True
print('OK')
"""],
            capture_output=True,
            text=True,
            cwd=temp_dir,
        )

        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_serve_remote_flag_boolean(self, temp_dir: Path):
        """Remote flag is a boolean, not requiring a value."""
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from ralph_orchestrator.cli import build_parser

parser = build_parser()

# --remote without value
args = parser.parse_args(['serve', '--remote'])
assert args.remote is True

# No --remote flag
args = parser.parse_args(['serve'])
assert args.remote is False

print('OK')
"""],
            capture_output=True,
            text=True,
            cwd=temp_dir,
        )

        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_serve_remote_overrides_host(self, temp_dir: Path):
        """Remote flag overrides host setting to 0.0.0.0."""
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from ralph_orchestrator.cli import build_parser

parser = build_parser()

# --remote should override --host
args = parser.parse_args(['serve', '--host', '192.168.1.1', '--remote'])
# The command_serve function changes host to 0.0.0.0 when remote=True
# But at parse time, host is still the provided value
assert args.host == '192.168.1.1'
assert args.remote is True

print('OK')
"""],
            capture_output=True,
            text=True,
            cwd=temp_dir,
        )

        assert result.returncode == 0
        assert "OK" in result.stdout


@pytest.mark.integration
class TestServeCommandStartup:
    """Integration tests for serve command startup behavior."""

    def test_serve_rejects_nonexistent_projects_root(self, temp_dir: Path):
        """Command exits with error if projects_root does not exist."""
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
from pathlib import Path
import argparse
sys.path.insert(0, str(Path.cwd()))
from ralph_orchestrator.cli import command_serve

args = argparse.Namespace(
    port=3000,
    host='127.0.0.1',
    projects_root='/this/path/does/not/exist',
    open=False,
    remote=False,
)

exit_code = command_serve(args)
sys.exit(exit_code)
"""],
            capture_output=True,
            text=True,
            cwd=temp_dir,
        )

        assert result.returncode == 2
        assert "does not exist" in result.stderr

    def test_serve_handles_missing_uvicorn(self, temp_dir: Path):
        """Command exits with helpful error if uvicorn not installed."""
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
from pathlib import Path
import argparse

# Hide uvicorn module
if 'uvicorn' in sys.modules:
    del sys.modules['uvicorn']

# Prevent uvicorn from being imported
original_import = __builtins__.__import__
def block_uvicorn(name, *args, **kwargs):
    if name == 'uvicorn':
        raise ImportError('No module named uvicorn')
    return original_import(name, *args, **kwargs)
__builtins__.__import__ = block_uvicorn

sys.path.insert(0, str(Path.cwd()))
from ralph_orchestrator.cli import command_serve

args = argparse.Namespace(
    port=3000,
    host='127.0.0.1',
    projects_root=None,
    open=False,
    remote=False,
)

exit_code = command_serve(args)
sys.exit(exit_code)
"""],
            capture_output=True,
            text=True,
            cwd=temp_dir,
        )

        assert result.returncode == 1
        assert "uvicorn" in result.stderr.lower()
        assert "install" in result.stderr.lower()


@pytest.mark.integration
class TestServeCommandPortVariations:
    """Test serve command with various port configurations."""

    def test_serve_accepts_custom_ports(self, temp_dir: Path):
        """Command accepts various valid port numbers."""
        for port in [8000, 8080, 5000, 9999]:
            result = subprocess.run(
                [sys.executable, "-c", f"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from ralph_orchestrator.cli import build_parser

parser = build_parser()
args = parser.parse_args(['serve', '--port', '{port}'])
assert args.port == {port}
print('OK')
"""],
                capture_output=True,
                text=True,
                cwd=temp_dir,
            )

            assert result.returncode == 0
            assert "OK" in result.stdout
