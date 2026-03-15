#!/usr/bin/env python3
"""
Test that no legacy imports are used.

Verifies that all Python files use modern 'almaapitk' imports
and not legacy patterns like 'from src.*', 'from client.*', 'from domains.*'.
"""

import ast
import unittest
from pathlib import Path


class TestNoLegacyImports(unittest.TestCase):
    """Verify no legacy imports are present in the codebase."""

    LEGACY_PATTERNS = [
        'src.',
        'client.',
        'domains.',
        'utils.',
    ]

    def get_python_files(self) -> list[Path]:
        """Get all Python files in the project."""
        project_root = Path(__file__).parent.parent
        return list(project_root.glob('**/*.py'))

    def extract_imports(self, filepath: Path) -> list[str]:
        """Extract all import strings from a Python file."""
        imports = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(filepath))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

        except SyntaxError:
            pass  # Skip files with syntax errors

        return imports

    def test_no_legacy_imports(self):
        """Check all Python files for legacy import patterns."""
        violations = []

        for filepath in self.get_python_files():
            # Skip test files themselves
            if 'test_' in filepath.name:
                continue

            imports = self.extract_imports(filepath)

            for imp in imports:
                for pattern in self.LEGACY_PATTERNS:
                    if imp.startswith(pattern):
                        violations.append((filepath.name, imp))

        if violations:
            message = "Legacy imports found:\n"
            for filename, import_name in violations:
                message += f"  - {filename}: {import_name}\n"
            self.fail(message)

    def test_uses_almaapitk(self):
        """Verify that almaapitk is used for Alma API imports."""
        found_almaapitk = False

        for filepath in self.get_python_files():
            imports = self.extract_imports(filepath)
            if any('almaapitk' in imp for imp in imports):
                found_almaapitk = True
                break

        self.assertTrue(
            found_almaapitk,
            "No files import from almaapitk - verify dependency is set up correctly"
        )


if __name__ == '__main__':
    unittest.main()
