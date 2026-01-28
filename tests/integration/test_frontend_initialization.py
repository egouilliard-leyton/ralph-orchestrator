"""
Integration tests for T-009: Initialize frontend Next.js application

Tests verify that the frontend directory is properly set up with:
- Next.js 15+ with TypeScript
- Tailwind CSS configuration
- shadcn/ui component library
- Proper project structure
- Build configuration outputting to server/static/
"""

import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def frontend_dir():
    """Return the frontend directory path."""
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "frontend"


@pytest.fixture
def package_json(frontend_dir):
    """Load and return package.json contents."""
    package_json_path = frontend_dir / "package.json"
    assert package_json_path.exists(), "package.json does not exist"
    with open(package_json_path) as f:
        return json.load(f)


class TestFrontendDirectory:
    """Test frontend directory structure and configuration files."""

    def test_frontend_directory_exists(self, frontend_dir):
        """Verify frontend/ directory exists at repository root."""
        assert frontend_dir.exists(), "frontend/ directory does not exist"
        assert frontend_dir.is_dir(), "frontend/ is not a directory"

    def test_package_json_exists(self, package_json):
        """Verify package.json exists and is valid JSON."""
        assert package_json is not None
        assert isinstance(package_json, dict)

    def test_typescript_config_exists(self, frontend_dir):
        """Verify tsconfig.json exists and is valid."""
        tsconfig_path = frontend_dir / "tsconfig.json"
        assert tsconfig_path.exists(), "tsconfig.json does not exist"

        with open(tsconfig_path) as f:
            tsconfig = json.load(f)

        # Verify strict mode is enabled
        assert tsconfig.get("compilerOptions", {}).get("strict") is True, \
            "TypeScript strict mode should be enabled"

    def test_next_config_exists(self, frontend_dir):
        """Verify next.config.ts exists."""
        next_config_path = frontend_dir / "next.config.ts"
        assert next_config_path.exists(), "next.config.ts does not exist"

    def test_components_json_exists(self, frontend_dir):
        """Verify shadcn/ui components.json exists."""
        components_json_path = frontend_dir / "components.json"
        assert components_json_path.exists(), "components.json does not exist"


class TestDependencies:
    """Test package.json dependencies meet requirements."""

    def test_nextjs_version(self, package_json):
        """Verify Next.js 15+ is installed."""
        next_version = package_json.get("dependencies", {}).get("next")
        assert next_version is not None, "next is not in dependencies"

        # Extract major version (handles formats like "^15.0.0", "15.1.5", "~15.0.0")
        major_version = int(next_version.strip("^~").split(".")[0])
        assert major_version >= 15, f"Next.js version should be 15+, got {next_version}"

    def test_react_version(self, package_json):
        """Verify React 19+ is installed."""
        react_version = package_json.get("dependencies", {}).get("react")
        assert react_version is not None, "react is not in dependencies"

        major_version = int(react_version.strip("^~").split(".")[0])
        assert major_version >= 19, f"React version should be 19+, got {react_version}"

    def test_typescript_installed(self, package_json):
        """Verify TypeScript is in devDependencies."""
        typescript = package_json.get("devDependencies", {}).get("typescript")
        assert typescript is not None, "typescript is not in devDependencies"

    def test_tailwindcss_installed(self, package_json):
        """Verify Tailwind CSS is installed."""
        tailwind = package_json.get("devDependencies", {}).get("tailwindcss")
        assert tailwind is not None, "tailwindcss is not in devDependencies"

    def test_shadcn_dependencies_installed(self, package_json):
        """Verify shadcn/ui related dependencies are installed."""
        deps = package_json.get("dependencies", {})

        # Check for key shadcn/ui dependencies
        assert "class-variance-authority" in deps, "class-variance-authority not installed"
        assert "clsx" in deps, "clsx not installed"
        assert "tailwind-merge" in deps, "tailwind-merge not installed"

        # Check for at least some Radix UI components
        radix_components = [key for key in deps.keys() if key.startswith("@radix-ui/")]
        assert len(radix_components) > 0, "No Radix UI components found"


class TestProjectStructure:
    """Test directory structure matches requirements."""

    def test_src_directory_exists(self, frontend_dir):
        """Verify src/ directory exists."""
        src_dir = frontend_dir / "src"
        assert src_dir.exists(), "src/ directory does not exist"

    def test_components_directory_exists(self, frontend_dir):
        """Verify src/components/ directory exists with UI components."""
        components_dir = frontend_dir / "src" / "components"
        assert components_dir.exists(), "src/components/ directory does not exist"

        # Check for ui subdirectory (shadcn/ui components)
        ui_dir = components_dir / "ui"
        assert ui_dir.exists(), "src/components/ui/ directory does not exist"

        # Verify at least some UI components exist
        ui_components = list(ui_dir.glob("*.tsx"))
        assert len(ui_components) > 0, "No UI components found in src/components/ui/"

    def test_app_directory_exists(self, frontend_dir):
        """Verify src/app/ directory exists (Next.js app router)."""
        app_dir = frontend_dir / "src" / "app"
        assert app_dir.exists(), "src/app/ directory does not exist"

        # Verify core app files
        assert (app_dir / "layout.tsx").exists(), "src/app/layout.tsx does not exist"
        assert (app_dir / "page.tsx").exists(), "src/app/page.tsx does not exist"

    def test_services_directory_exists(self, frontend_dir):
        """Verify src/services/ directory exists with api.ts."""
        services_dir = frontend_dir / "src" / "services"
        assert services_dir.exists(), "src/services/ directory does not exist"

        api_file = services_dir / "api.ts"
        assert api_file.exists(), "src/services/api.ts does not exist"

    def test_hooks_directory_exists(self, frontend_dir):
        """Verify src/hooks/ directory exists."""
        hooks_dir = frontend_dir / "src" / "hooks"
        assert hooks_dir.exists(), "src/hooks/ directory does not exist"


class TestAPIClient:
    """Test the API client implementation."""

    def test_api_client_exports(self, frontend_dir):
        """Verify api.ts exports required interfaces and client."""
        api_file = frontend_dir / "src" / "services" / "api.ts"
        content = api_file.read_text()

        # Check for key exports
        assert "export const api" in content, "api client not exported"
        assert "export interface Project" in content, "Project interface not exported"
        assert "export interface Task" in content, "Task interface not exported"
        assert "export interface Session" in content, "Session interface not exported"
        assert "ApiError" in content, "ApiError class not defined"

    def test_api_client_structure(self, frontend_dir):
        """Verify api client has expected methods."""
        api_file = frontend_dir / "src" / "services" / "api.ts"
        content = api_file.read_text()

        # Check for main API sections
        assert "health:" in content, "health endpoint not defined"
        assert "projects:" in content, "projects endpoints not defined"
        assert "tasks:" in content, "tasks endpoints not defined"
        assert "sessions:" in content, "sessions endpoints not defined"


class TestBuildConfiguration:
    """Test Next.js build configuration."""

    def test_next_config_output_directory(self, frontend_dir):
        """Verify next.config.ts configures output to ../ralph_orchestrator/server/static/."""
        next_config_path = frontend_dir / "next.config.ts"
        content = next_config_path.read_text()

        # Check for static export configuration
        assert 'output: "export"' in content, "Static export not configured"
        assert '../ralph_orchestrator/server/static' in content, \
            "Output directory not set to ../ralph_orchestrator/server/static"

    def test_server_static_directory_in_tsconfig_exclude(self, frontend_dir):
        """Verify server/static directory is excluded from TypeScript compilation."""
        tsconfig_path = frontend_dir / "tsconfig.json"
        with open(tsconfig_path) as f:
            tsconfig = json.load(f)

        exclude = tsconfig.get("exclude", [])
        assert any("server/static" in path for path in exclude), \
            "server/static should be in tsconfig.json exclude"


class TestScripts:
    """Test package.json scripts."""

    def test_dev_script_exists(self, package_json):
        """Verify dev script exists and runs on port 3001."""
        scripts = package_json.get("scripts", {})
        dev_script = scripts.get("dev")

        assert dev_script is not None, "dev script does not exist"
        assert "next dev" in dev_script, "dev script should run next dev"
        assert "3001" in dev_script, "dev script should use port 3001"

    def test_build_script_exists(self, package_json):
        """Verify build script exists."""
        scripts = package_json.get("scripts", {})
        build_script = scripts.get("build")

        assert build_script is not None, "build script does not exist"
        assert "next build" in build_script, "build script should run next build"

    def test_start_script_exists(self, package_json):
        """Verify start script exists."""
        scripts = package_json.get("scripts", {})
        assert "start" in scripts, "start script does not exist"


class TestTailwindConfiguration:
    """Test Tailwind CSS configuration."""

    def test_globals_css_exists(self, frontend_dir):
        """Verify globals.css exists with Tailwind imports."""
        globals_css = frontend_dir / "src" / "app" / "globals.css"
        assert globals_css.exists(), "src/app/globals.css does not exist"

        content = globals_css.read_text()
        assert "@import" in content and "tailwindcss" in content, \
            "Tailwind CSS not imported in globals.css"

    def test_design_system_variables(self, frontend_dir):
        """Verify design system CSS variables are defined."""
        globals_css = frontend_dir / "src" / "app" / "globals.css"
        content = globals_css.read_text()

        # Check for key design tokens
        assert "--primary" in content, "Primary color variable not defined"
        assert "--secondary" in content, "Secondary color variable not defined"
        assert "--border" in content, "Border color variable not defined"
        assert "--radius" in content, "Border radius variable not defined"


class TestShadcnUI:
    """Test shadcn/ui component library setup."""

    def test_components_json_configuration(self, frontend_dir):
        """Verify components.json is properly configured."""
        components_json_path = frontend_dir / "components.json"
        with open(components_json_path) as f:
            config = json.load(f)

        assert config.get("tsx") is True, "tsx should be enabled"
        assert config.get("rsc") is True, "React Server Components should be enabled"

        # Verify aliases
        aliases = config.get("aliases", {})
        assert "@/components" in aliases.get("components", ""), \
            "components alias not configured"
        assert "@/lib/utils" in aliases.get("utils", ""), \
            "utils alias not configured"

    def test_ui_components_installed(self, frontend_dir):
        """Verify shadcn/ui components are installed."""
        ui_dir = frontend_dir / "src" / "components" / "ui"

        # Check for common shadcn/ui components
        expected_components = ["button.tsx", "card.tsx", "input.tsx"]
        for component in expected_components:
            component_path = ui_dir / component
            assert component_path.exists(), f"{component} not found in ui components"

    def test_utils_file_exists(self, frontend_dir):
        """Verify lib/utils.ts exists (required for shadcn/ui)."""
        utils_file = frontend_dir / "src" / "lib" / "utils.ts"
        assert utils_file.exists(), "src/lib/utils.ts does not exist"

        # Verify it exports cn utility
        content = utils_file.read_text()
        assert "export" in content and "cn" in content, \
            "cn utility function not exported from utils.ts"
