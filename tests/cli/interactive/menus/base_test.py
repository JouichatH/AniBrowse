"""
Base test utilities for interactive menu testing.
Provides common patterns and utilities following DRY principles.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Any, Optional, Dict, List

from fastanime.cli.interactive.state import State, ControlFlow
from fastanime.cli.interactive.session import Context


class BaseMenuTest:
    """
    Base class for menu tests providing common testing patterns and utilities.
    Follows DRY principles by centralizing common test logic.
    """
    
    @pytest.fixture(autouse=True)
    def setup_base_mocks(self, mock_create_feedback_manager, mock_rich_console):
        """Automatically set up common mocks for all menu tests."""
        self.mock_feedback = mock_create_feedback_manager
        self.mock_console = mock_rich_console
    
    def assert_exit_behavior(self, result: Any):
        """Assert that the menu returned EXIT control flow."""
        assert isinstance(result, ControlFlow)
        assert result == ControlFlow.EXIT
    
    def assert_back_behavior(self, result: Any):
        """Assert that the menu returned BACK control flow."""
        assert isinstance(result, ControlFlow)
        assert result == ControlFlow.BACK
    
    def assert_continue_behavior(self, result: Any):
        """Assert that the menu returned CONTINUE control flow."""
        assert isinstance(result, ControlFlow)
        assert result == ControlFlow.CONTINUE
    
    def assert_reload_config_behavior(self, result: Any):
        """Assert that the menu returned RELOAD_CONFIG control flow."""
        assert isinstance(result, ControlFlow)
        assert result == ControlFlow.RELOAD_CONFIG
    
    def assert_menu_transition(self, result: Any, expected_menu: str):
        """Assert that the menu transitioned to the expected menu state."""
        assert isinstance(result, State)
        assert result.menu_name == expected_menu
    
    def setup_selector_choice(self, context: Context, choice: Optional[str]):
        """Helper to configure selector choice return value."""
        context.selector.choose.return_value = choice
    
    def setup_selector_input(self, context: Context, input_value: str):
        """Helper to configure selector input return value."""
        context.selector.input.return_value = input_value
    
    def setup_selector_confirm(self, context: Context, confirm: bool):
        """Helper to configure selector confirm return value."""
        context.selector.confirm.return_value = confirm
    
    def setup_feedback_confirm(self, confirm: bool):
        """Helper to configure feedback confirm return value."""
        self.mock_feedback.confirm.return_value = confirm
    
    def assert_console_cleared(self):
        """Assert that the console was cleared."""
        self.mock_console.clear.assert_called_once()
    
    def assert_feedback_error_called(self, message_contains: str = None):
        """Assert that feedback.error was called, optionally with specific message."""
        self.mock_feedback.error.assert_called()
        if message_contains:
            call_args = self.mock_feedback.error.call_args
            assert message_contains in str(call_args)
    
    def assert_feedback_info_called(self, message_contains: str = None):
        """Assert that feedback.info was called, optionally with specific message."""
        self.mock_feedback.info.assert_called()
        if message_contains:
            call_args = self.mock_feedback.info.call_args
            assert message_contains in str(call_args)
    
    def assert_feedback_warning_called(self, message_contains: str = None):
        """Assert that feedback.warning was called, optionally with specific message."""
        self.mock_feedback.warning.assert_called()
        if message_contains:
            call_args = self.mock_feedback.warning.call_args
            assert message_contains in str(call_args)
    
    def assert_feedback_success_called(self, message_contains: str = None):
        """Assert that feedback.success was called, optionally with specific message."""
        self.mock_feedback.success.assert_called()
        if message_contains:
            call_args = self.mock_feedback.success.call_args
            assert message_contains in str(call_args)
    
    def create_test_options_dict(self, base_options: Dict[str, str], icons: bool = True) -> Dict[str, str]:
        """
        Helper to create options dictionary with or without icons.
        Useful for testing both icon and non-icon configurations.
        """
        if not icons:
            # Remove emoji icons from options
            return {key: value.split(' ', 1)[-1] if ' ' in value else value 
                   for key, value in base_options.items()}
        return base_options
    
    def get_menu_choices(self, options_dict: Dict[str, str]) -> List[str]:
        """Extract the choice strings from an options dictionary."""
        return list(options_dict.values())
    
    def simulate_user_choice(self, context: Context, choice_key: str, options_dict: Dict[str, str]):
        """Simulate a user making a specific choice from the menu options."""
        choice_value = options_dict.get(choice_key)
        if choice_value:
            self.setup_selector_choice(context, choice_value)
        return choice_value


class MenuTestMixin:
    """
    Mixin providing additional test utilities that can be combined with BaseMenuTest.
    Useful for specialized menu testing scenarios.
    """
    
    def setup_api_search_result(self, context: Context, search_result: Any):
        """Configure the API client to return a specific search result."""
        context.media_api.search_media.return_value = search_result
    
    def setup_api_search_failure(self, context: Context):
        """Configure the API client to fail search requests."""
        context.media_api.search_media.return_value = None
    
    def setup_provider_search_result(self, context: Context, search_result: Any):
        """Configure the provider to return a specific search result."""
        context.provider.search.return_value = search_result
    
    def setup_provider_search_failure(self, context: Context):
        """Configure the provider to fail search requests."""
        context.provider.search.return_value = None
    
    def setup_authenticated_user(self, context: Context, user_profile: Any):
        """Configure the context for an authenticated user."""
        context.media_api.user_profile = user_profile
    
    def setup_unauthenticated_user(self, context: Context):
        """Configure the context for an unauthenticated user."""
        context.media_api.user_profile = None
    
    def verify_selector_called_with_choices(self, context: Context, expected_choices: List[str]):
        """Verify that the selector was called with the expected choices."""
        context.selector.choose.assert_called_once()
        call_args = context.selector.choose.call_args
        actual_choices = call_args[1]['choices']  # Get choices from kwargs
        assert actual_choices == expected_choices
    
    def verify_selector_prompt(self, context: Context, expected_prompt: str):
        """Verify that the selector was called with the expected prompt."""
        context.selector.choose.assert_called_once()
        call_args = context.selector.choose.call_args
        actual_prompt = call_args[1]['prompt']  # Get prompt from kwargs
        assert actual_prompt == expected_prompt


class AuthMenuTestMixin(MenuTestMixin):
    """Specialized mixin for authentication menu tests."""
    
    def setup_auth_manager_mock(self):
        """Set up AuthManager mock for authentication tests."""
        with patch('fastanime.cli.auth.manager.AuthManager') as mock_auth:
            auth_instance = Mock()
            auth_instance.load_user_profile.return_value = None
            auth_instance.save_user_profile.return_value = True
            auth_instance.clear_user_profile.return_value = True
            mock_auth.return_value = auth_instance
            return auth_instance
    
    def setup_webbrowser_mock(self):
        """Set up webbrowser.open mock for authentication tests."""
        return patch('webbrowser.open')


class SessionMenuTestMixin(MenuTestMixin):
    """Specialized mixin for session management menu tests."""
    
    def setup_session_manager_mock(self):
        """Set up session manager mock for session tests."""
        session_manager = Mock()
        session_manager.list_saved_sessions.return_value = []
        session_manager.save_session.return_value = True
        session_manager.load_session.return_value = []
        session_manager.cleanup_old_sessions.return_value = 0
        return session_manager
    
    def setup_path_exists_mock(self, exists: bool = True):
        """Set up Path.exists mock for file system tests."""
        return patch('pathlib.Path.exists', return_value=exists)


class MediaMenuTestMixin(MenuTestMixin):
    """Specialized mixin for media-related menu tests."""
    
    def setup_media_list_success(self, context: Context, media_result: Any):
        """Set up successful media list fetch."""
        self.setup_api_search_result(context, media_result)
    
    def setup_media_list_failure(self, context: Context):
        """Set up failed media list fetch."""
        self.setup_api_search_failure(context)
    
    def create_mock_media_result(self, num_items: int = 1):
        """Create a mock media search result with specified number of items."""
        from fastanime.libs.api.types import MediaSearchResult, MediaItem
        
        media_items = []
        for i in range(num_items):
            media_items.append(MediaItem(
                id=i + 1,
                title=f"Test Anime {i + 1}",
                description=f"Description for test anime {i + 1}",
                cover_image=f"https://example.com/cover{i + 1}.jpg",
                banner_image=f"https://example.com/banner{i + 1}.jpg",
                status="RELEASING",
                episodes=12,
                duration=24,
                genres=["Action", "Adventure"],
                mean_score=85 + i,
                popularity=1000 + i * 100,
                start_date="2024-01-01",
                end_date=None
            ))
        
        return MediaSearchResult(
            media=media_items,
            page_info={
                "total": num_items,
                "current_page": 1,
                "last_page": 1,
                "has_next_page": False,
                "per_page": 20
            }
        )
