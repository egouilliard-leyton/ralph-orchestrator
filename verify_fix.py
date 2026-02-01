#!/usr/bin/env python3
"""Quick verification that the test fix is correct."""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

def test_dependency_graph_extractable():
    """Verify that dependency graph can be extracted for documentation."""
    cli_path = PROJECT_ROOT / "ralph_orchestrator/cli.py"
    content = cli_path.read_text()
    tree = ast.parse(content)

    # Extract all imports (both relative and absolute)
    dependencies = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # Relative imports have level > 0 (e.g., from .run import X has level=1)
            # The module name does NOT include the leading dot(s)
            if node.level > 0:
                # This is a relative import
                if node.module:
                    dependencies.append(node.module)
                else:
                    # from . import X - imports from current package
                    for alias in node.names:
                        dependencies.append(alias.name)

    print(f"Dependencies found: {dependencies}")
    print(f"Count: {len(dependencies)}")

    # Should have internal dependencies that can be documented
    assert len(dependencies) > 0, \
        "Should be able to extract dependency graph"

    print("TEST PASSED!")

if __name__ == "__main__":
    test_dependency_graph_extractable()
