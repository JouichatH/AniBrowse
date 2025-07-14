"""
Test runner for all interactive menu tests.
This file can be used to run all menu tests at once or specific test suites.
"""

import pytest
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def run_all_menu_tests():
    """Run all menu tests."""
    test_dir = Path(__file__).parent
    return pytest.main([str(test_dir), "-v"])


def run_specific_menu_test(menu_name: str):
    """Run tests for a specific menu."""
    test_file = Path(__file__).parent / f"test_{menu_name}.py"
    if test_file.exists():
        return pytest.main([str(test_file), "-v"])
    else:
        print(f"Test file for menu '{menu_name}' not found.")
        return 1


def run_menu_test_with_coverage():
    """Run menu tests with coverage report."""
    test_dir = Path(__file__).parent
    return pytest.main([
        str(test_dir),
        "--cov=fastanime.cli.interactive.menus",
        "--cov-report=html",
        "--cov-report=term-missing",
        "-v"
    ])


def run_integration_tests():
    """Run integration tests that require network connectivity."""
    test_dir = Path(__file__).parent
    return pytest.main([str(test_dir), "-m", "integration", "-v"])


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run interactive menu tests")
    parser.add_argument(
        "--menu", 
        help="Run tests for a specific menu",
        choices=[
            "main", "results", "auth", "media_actions", "episodes", 
            "servers", "player_controls", "provider_search", 
            "session_management", "watch_history"
        ]
    )
    parser.add_argument(
        "--coverage", 
        action="store_true", 
        help="Run tests with coverage report"
    )
    parser.add_argument(
        "--integration", 
        action="store_true", 
        help="Run integration tests only"
    )
    
    args = parser.parse_args()
    
    if args.integration:
        exit_code = run_integration_tests()
    elif args.coverage:
        exit_code = run_menu_test_with_coverage()
    elif args.menu:
        exit_code = run_specific_menu_test(args.menu)
    else:
        exit_code = run_all_menu_tests()
    
    sys.exit(exit_code)
