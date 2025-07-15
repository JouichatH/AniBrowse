# Interactive Menu Tests

This directory contains comprehensive tests for FastAnime's interactive CLI menus. The test suite follows DRY principles and provides extensive coverage of all menu functionality.

## Test Structure

```
tests/
├── conftest.py                          # Shared fixtures and test configuration
├── cli/
│   └── interactive/
│       ├── test_session.py              # Session management tests
│       └── menus/
│           ├── base_test.py             # Base test classes and utilities
│           ├── test_main.py             # Main menu tests
│           ├── test_auth.py             # Authentication menu tests
│           ├── test_session_management.py  # Session management menu tests
│           ├── test_results.py          # Results display menu tests
│           ├── test_episodes.py         # Episodes selection menu tests
│           ├── test_watch_history.py    # Watch history menu tests
│           ├── test_media_actions.py    # Media actions menu tests
│           └── test_additional_menus.py # Additional menus (servers, provider search, etc.)
```

## Test Architecture

### Base Classes

- **`BaseMenuTest`**: Core test functionality for all menu tests
  - Console clearing verification
  - Control flow assertions (BACK, EXIT, CONTINUE, RELOAD_CONFIG)
  - Menu transition assertions
  - Feedback message verification
  - Common setup patterns

- **`MenuTestMixin`**: Additional utilities for specialized testing
  - API result mocking
  - Authentication state setup
  - Provider search configuration

- **Specialized Mixins**:
  - `AuthMenuTestMixin`: Authentication-specific test utilities
  - `SessionMenuTestMixin`: Session management test utilities
  - `MediaMenuTestMixin`: Media-related test utilities

### Fixtures

**Core Fixtures** (in `conftest.py`):
- `mock_config`: Application configuration
- `mock_context`: Complete context with all dependencies
- `mock_unauthenticated_context`: Context without authentication
- `mock_user_profile`: Authenticated user data
- `mock_media_item`: Sample anime/media data
- `mock_media_search_result`: API search results
- `basic_state`: Basic menu state
- `state_with_media_data`: State with media information

**Utility Fixtures**:
- `mock_feedback_manager`: User feedback system
- `mock_console`: Rich console output
- `menu_helper`: Helper methods for common test patterns

## Test Categories

### Unit Tests
Each menu has comprehensive unit tests covering:
- Navigation choices and transitions
- Error handling and edge cases
- Authentication requirements
- Configuration variations (icons enabled/disabled)
- Input validation
- API interaction patterns

### Integration Tests
Tests covering menu flow and interaction:
- Complete navigation workflows
- Error recovery across menus
- Authentication flow integration
- Session state persistence

### Test Patterns

#### Navigation Testing
```python
def test_menu_navigation(self, mock_context, basic_state):
    self.setup_selector_choice(mock_context, "Target Option")
    result = menu_function(mock_context, basic_state)
    self.assert_menu_transition(result, "TARGET_MENU")
```

#### Error Handling Testing
```python
def test_menu_error_handling(self, mock_context, basic_state):
    self.setup_api_failure(mock_context)
    result = menu_function(mock_context, basic_state)
    self.assert_continue_behavior(result)
    self.assert_feedback_error_called("Expected error message")
```

#### Authentication Testing
```python
def test_authenticated_vs_unauthenticated(self, mock_context, mock_unauthenticated_context, basic_state):
    # Test authenticated behavior
    result1 = menu_function(mock_context, basic_state)
    # Test unauthenticated behavior  
    result2 = menu_function(mock_unauthenticated_context, basic_state)
    # Assert different behaviors
```

## Running Tests

### Quick Start
```bash
# Run all interactive menu tests
python -m pytest tests/cli/interactive/ -v

# Run tests with coverage
python -m pytest tests/cli/interactive/ --cov=fastanime.cli.interactive --cov-report=html

# Run specific menu tests
python -m pytest tests/cli/interactive/menus/test_main.py -v
```

### Using the Test Runner
```bash
# Quick unit tests
./run_tests.py --quick

# Full test suite with coverage and linting
./run_tests.py --full

# Test specific menu
./run_tests.py --menu main

# Test with pattern matching
./run_tests.py --pattern "test_auth" --verbose

# Generate coverage report only
./run_tests.py --coverage-only
```

### Test Runner Options
- `--quick`: Fast unit tests only
- `--full`: Complete suite with coverage and linting
- `--menu <name>`: Test specific menu
- `--pattern <pattern>`: Match test names
- `--coverage`: Generate coverage reports
- `--verbose`: Detailed output
- `--fail-fast`: Stop on first failure
- `--parallel <n>`: Run tests in parallel
- `--lint`: Run code linting

## Test Coverage Goals

The test suite aims for comprehensive coverage of:

- ✅ **Menu Navigation**: All menu choices and transitions
- ✅ **Error Handling**: API failures, invalid input, edge cases
- ✅ **Authentication Flow**: Authenticated vs unauthenticated behavior
- ✅ **Configuration Variations**: Icons, providers, preferences
- ✅ **User Input Validation**: Empty input, invalid formats, special characters
- ✅ **State Management**: Session state persistence and recovery
- ✅ **Control Flow**: BACK, EXIT, CONTINUE, RELOAD_CONFIG behaviors
- ✅ **Integration Points**: Menu-to-menu transitions and data flow

## Adding New Tests

### For New Menus
1. Create `test_<menu_name>.py` in `tests/cli/interactive/menus/`
2. Inherit from `BaseMenuTest` and appropriate mixins
3. Follow the established patterns for navigation, error handling, and authentication testing
4. Add fixtures specific to the menu's data requirements

### For New Features
1. Add tests to existing menu test files
2. Create new fixtures in `conftest.py` if needed
3. Add new test patterns to `base_test.py` if reusable
4. Update this README with new patterns or conventions

### Test Naming Conventions
- `test_<menu>_<scenario>`: Basic functionality tests
- `test_<menu>_<action>_success`: Successful operation tests  
- `test_<menu>_<action>_failure`: Error condition tests
- `test_<menu>_<condition>_<behavior>`: Conditional behavior tests

## Debugging Tests

### Common Issues
- **Import Errors**: Ensure all dependencies are properly mocked
- **State Errors**: Verify state fixtures have required data
- **Mock Configuration**: Check that mocks match actual interface contracts
- **Async Issues**: Ensure async operations are properly handled in tests

### Debugging Tools
```bash
# Run specific test with debug output
python -m pytest tests/cli/interactive/menus/test_main.py::TestMainMenu::test_specific_case -v -s

# Run with Python debugger
python -m pytest --pdb tests/cli/interactive/menus/test_main.py

# Generate detailed coverage report
python -m pytest --cov=fastanime.cli.interactive --cov-report=html --cov-report=term-missing -v
```

## Continuous Integration

The test suite is designed for CI/CD integration:
- Fast unit tests for quick feedback
- Comprehensive integration tests for release validation
- Coverage reporting for quality metrics
- Linting integration for code quality

### CI Configuration Example
```yaml
# Run quick tests on every commit
pytest tests/cli/interactive/ -m unit --fail-fast

# Run full suite on PR/release
pytest tests/cli/interactive/ --cov=fastanime.cli.interactive --cov-fail-under=90
```
