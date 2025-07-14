# Interactive Menu Tests

This directory contains comprehensive test suites for all interactive menu functionality in FastAnime.

## Test Structure

```
tests/interactive/menus/
├── conftest.py                    # Shared fixtures and utilities
├── __init__.py                    # Package marker
├── run_tests.py                   # Test runner script
├── README.md                      # This file
├── test_main.py                   # Tests for main menu
├── test_results.py                # Tests for results menu
├── test_auth.py                   # Tests for authentication menu
├── test_media_actions.py          # Tests for media actions menu
├── test_episodes.py               # Tests for episodes menu
├── test_servers.py                # Tests for servers menu
├── test_player_controls.py        # Tests for player controls menu
├── test_provider_search.py        # Tests for provider search menu
├── test_session_management.py     # Tests for session management menu
└── test_watch_history.py          # Tests for watch history menu
```

## Test Categories

### Unit Tests

Each menu has its own comprehensive test file that covers:

- Menu display and option rendering
- User interaction handling
- State transitions
- Error handling
- Configuration options (icons, preferences)
- Helper function testing

### Integration Tests

Tests marked with `@pytest.mark.integration` require network connectivity and test:

- Real API interactions
- Authentication flows
- Data fetching and processing

## Test Coverage

Each test file covers the following aspects:

### Main Menu Tests (`test_main.py`)

- Option display with/without icons
- Navigation to different categories (trending, popular, etc.)
- Search functionality
- User list access (authenticated/unauthenticated)
- Authentication and session management
- Configuration editing
- Helper function testing

### Results Menu Tests (`test_results.py`)

- Search result display
- Pagination handling
- Anime selection
- Preview functionality
- Authentication status display
- Helper function testing

### Authentication Menu Tests (`test_auth.py`)

- Login/logout flows
- OAuth authentication
- Token input handling
- Profile display
- Authentication status management
- Helper function testing

### Media Actions Menu Tests (`test_media_actions.py`)

- Action menu display
- Streaming initiation
- Trailer playback
- List management
- Scoring functionality
- Local history tracking
- Information display
- Helper function testing

### Episodes Menu Tests (`test_episodes.py`)

- Episode list display
- Watch history continuation
- Episode selection
- Translation type handling
- Progress tracking
- Helper function testing

### Servers Menu Tests (`test_servers.py`)

- Server fetching and display
- Server selection
- Quality filtering
- Auto-server selection
- Player integration
- Error handling
- Helper function testing

### Player Controls Menu Tests (`test_player_controls.py`)

- Post-playback options
- Next episode handling
- Auto-next functionality
- Progress tracking
- Replay functionality
- Server switching
- Helper function testing

### Provider Search Menu Tests (`test_provider_search.py`)

- Provider anime search
- Auto-selection based on similarity
- Manual selection handling
- Preview integration
- Error handling
- Helper function testing

### Session Management Menu Tests (`test_session_management.py`)

- Session saving/loading
- Session listing and statistics
- Session deletion
- Auto-save configuration
- Backup creation
- Helper function testing

### Watch History Menu Tests (`test_watch_history.py`)

- History display and navigation
- History management (clear, export, import)
- Statistics calculation
- Anime selection from history
- Helper function testing

## Fixtures and Utilities

### Shared Fixtures (`conftest.py`)

- `mock_config`: Mock application configuration
- `mock_provider`: Mock anime provider
- `mock_selector`: Mock UI selector
- `mock_player`: Mock media player
- `mock_media_api`: Mock API client
- `mock_context`: Complete mock context
- `sample_media_item`: Sample AniList anime data
- `sample_provider_anime`: Sample provider anime data
- `sample_search_results`: Sample search results
- Various state fixtures for different scenarios

### Test Utilities

- `assert_state_transition()`: Assert proper state transitions
- `assert_control_flow()`: Assert control flow returns
- `setup_selector_choices()`: Configure mock selector choices
- `setup_selector_inputs()`: Configure mock selector inputs

## Running Tests

### Run All Menu Tests

```bash
python tests/interactive/menus/run_tests.py
```

### Run Specific Menu Tests

```bash
python tests/interactive/menus/run_tests.py --menu main
python tests/interactive/menus/run_tests.py --menu auth
python tests/interactive/menus/run_tests.py --menu episodes
```

### Run with Coverage

```bash
python tests/interactive/menus/run_tests.py --coverage
```

### Run Integration Tests Only

```bash
python tests/interactive/menus/run_tests.py --integration
```

### Using pytest directly

```bash
# Run all menu tests
pytest tests/interactive/menus/ -v

# Run specific test file
pytest tests/interactive/menus/test_main.py -v

# Run with coverage
pytest tests/interactive/menus/ --cov=fastanime.cli.interactive.menus --cov-report=html

# Run integration tests only
pytest tests/interactive/menus/ -m integration

# Run specific test class
pytest tests/interactive/menus/test_main.py::TestMainMenu -v

# Run specific test method
pytest tests/interactive/menus/test_main.py::TestMainMenu::test_main_menu_displays_options -v
```

## Test Patterns

### Menu Function Testing

```python
def test_menu_function(self, mock_context, test_state):
    """Test the menu function with specific setup."""
    # Setup
    mock_context.selector.choose.return_value = "Expected Choice"

    # Execute
    result = menu_function(mock_context, test_state)

    # Assert
    assert isinstance(result, State)
    assert result.menu_name == "EXPECTED_STATE"
```

### Error Handling Testing

```python
def test_menu_error_handling(self, mock_context, test_state):
    """Test menu handles errors gracefully."""
    # Setup error condition
    mock_context.provider.some_method.side_effect = Exception("Test error")

    # Execute
    result = menu_function(mock_context, test_state)

    # Assert error handling
    assert result == ControlFlow.BACK  # or appropriate error response
```

### State Transition Testing

```python
def test_state_transition(self, mock_context, initial_state):
    """Test proper state transitions."""
    # Setup
    mock_context.selector.choose.return_value = "Next State Option"

    # Execute
    result = menu_function(mock_context, initial_state)

    # Assert state transition
    assert_state_transition(result, "NEXT_STATE")
    assert result.media_api.anime == initial_state.media_api.anime  # State preservation
```

## Mocking Strategies

### API Mocking

```python
# Mock successful API calls
mock_context.media_api.search_media.return_value = sample_search_results

# Mock API failures
mock_context.media_api.search_media.side_effect = Exception("API Error")
```

### User Input Mocking

```python
# Mock menu selection
mock_context.selector.choose.return_value = "Selected Option"

# Mock text input
mock_context.selector.ask.return_value = "User Input"

# Mock cancelled selections
mock_context.selector.choose.return_value = None
```

### Configuration Mocking

```python
# Mock configuration options
mock_context.config.general.icons = True
mock_context.config.stream.auto_next = False
mock_context.config.anilist.per_page = 15
```

## Adding New Tests

When adding tests for new menus:

1. Create a new test file: `test_[menu_name].py`
2. Import the menu function and required fixtures
3. Create test classes for the main menu and helper functions
4. Follow the established patterns for testing:
   - Menu display and options
   - User interactions and selections
   - State transitions
   - Error handling
   - Configuration variations
   - Helper functions
5. Add the menu name to the choices in `run_tests.py`
6. Update this README with the new test coverage

## Best Practices

1. **Test Isolation**: Each test should be independent and not rely on other tests
2. **Clear Naming**: Test names should clearly describe what is being tested
3. **Comprehensive Coverage**: Test both happy paths and error conditions
4. **Realistic Mocks**: Mock data should represent realistic scenarios
5. **State Verification**: Always verify that state transitions are correct
6. **Error Testing**: Test error handling and edge cases
7. **Configuration Testing**: Test menu behavior with different configuration options
8. **Documentation**: Document complex test scenarios and mock setups

## Continuous Integration

These tests are designed to run in CI environments:

- Unit tests run without external dependencies
- Integration tests can be skipped in CI if needed
- Coverage reports help maintain code quality
- Fast execution for quick feedback loops
