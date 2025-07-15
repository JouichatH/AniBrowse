"""
Tests for the authentication menu.
Tests login, logout, profile viewing, and authentication flow.
"""

import pytest
from unittest.mock import Mock, patch

from fastanime.cli.interactive.menus.auth import auth
from fastanime.cli.interactive.state import State, ControlFlow

from .base_test import BaseMenuTest, AuthMenuTestMixin
from ...conftest import TEST_AUTH_OPTIONS


class TestAuthMenu(BaseMenuTest, AuthMenuTestMixin):
    """Test cases for the authentication menu."""
    
    def test_auth_menu_no_choice_goes_back(self, mock_context, basic_state):
        """Test that no choice selected results in BACK."""
        self.setup_selector_choice(mock_context, None)
        
        result = auth(mock_context, basic_state)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_auth_menu_back_choice(self, mock_context, basic_state):
        """Test explicit back choice."""
        self.setup_selector_choice(mock_context, TEST_AUTH_OPTIONS['back'])
        
        result = auth(mock_context, basic_state)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_auth_menu_unauthenticated_options(self, mock_unauthenticated_context, basic_state):
        """Test menu options when user is not authenticated."""
        self.setup_selector_choice(mock_unauthenticated_context, None)
        
        result = auth(mock_unauthenticated_context, basic_state)
        
        self.assert_back_behavior(result)
        # Verify correct options are shown for unauthenticated user
        mock_unauthenticated_context.selector.choose.assert_called_once()
        call_args = mock_unauthenticated_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # Should include login and help options
        assert any('Login' in choice for choice in choices)
        assert any('How to Get Token' in choice for choice in choices)
        assert any('Back' in choice for choice in choices)
        # Should not include logout or profile options
        assert not any('Logout' in choice for choice in choices)
        assert not any('Profile Details' in choice for choice in choices)
    
    def test_auth_menu_authenticated_options(self, mock_context, basic_state, mock_user_profile):
        """Test menu options when user is authenticated."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, None)
        
        result = auth(mock_context, basic_state)
        
        self.assert_back_behavior(result)
        # Verify correct options are shown for authenticated user
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # Should include logout and profile options
        assert any('Logout' in choice for choice in choices)
        assert any('Profile Details' in choice for choice in choices)
        assert any('Back' in choice for choice in choices)
        # Should not include login options
        assert not any('Login' in choice for choice in choices)
        assert not any('How to Get Token' in choice for choice in choices)
    
    def test_auth_menu_login_success(self, mock_unauthenticated_context, basic_state, mock_user_profile):
        """Test successful login flow."""
        self.setup_selector_choice(mock_unauthenticated_context, TEST_AUTH_OPTIONS['login'])
        self.setup_selector_input(mock_unauthenticated_context, "test_token_123")
        
        # Mock successful authentication
        mock_unauthenticated_context.media_api.authenticate.return_value = mock_user_profile
        
        with self.setup_auth_manager_mock() as mock_auth_manager:
            result = auth(mock_unauthenticated_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            # Verify authentication was attempted
            mock_unauthenticated_context.media_api.authenticate.assert_called_once_with("test_token_123")
            # Verify user profile was saved
            mock_auth_manager.save_user_profile.assert_called_once()
            self.assert_feedback_success_called("Successfully authenticated")
    
    def test_auth_menu_login_failure(self, mock_unauthenticated_context, basic_state):
        """Test failed login flow."""
        self.setup_selector_choice(mock_unauthenticated_context, TEST_AUTH_OPTIONS['login'])
        self.setup_selector_input(mock_unauthenticated_context, "invalid_token")
        
        # Mock failed authentication
        mock_unauthenticated_context.media_api.authenticate.return_value = None
        
        with self.setup_auth_manager_mock() as mock_auth_manager:
            result = auth(mock_unauthenticated_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            # Verify authentication was attempted
            mock_unauthenticated_context.media_api.authenticate.assert_called_once_with("invalid_token")
            # Verify user profile was not saved
            mock_auth_manager.save_user_profile.assert_not_called()
            self.assert_feedback_error_called("Authentication failed")
    
    def test_auth_menu_login_empty_token(self, mock_unauthenticated_context, basic_state):
        """Test login with empty token."""
        self.setup_selector_choice(mock_unauthenticated_context, TEST_AUTH_OPTIONS['login'])
        self.setup_selector_input(mock_unauthenticated_context, "")  # Empty token
        
        result = auth(mock_unauthenticated_context, basic_state)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        
        # Authentication should not be attempted with empty token
        mock_unauthenticated_context.media_api.authenticate.assert_not_called()
        self.assert_feedback_warning_called("Token cannot be empty")
    
    def test_auth_menu_logout_success(self, mock_context, basic_state, mock_user_profile):
        """Test successful logout flow."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, TEST_AUTH_OPTIONS['logout'])
        self.setup_feedback_confirm(True)  # Confirm logout
        
        with self.setup_auth_manager_mock() as mock_auth_manager:
            result = auth(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            # Verify logout confirmation was requested
            self.mock_feedback.confirm.assert_called_once()
            # Verify user profile was cleared
            mock_auth_manager.clear_user_profile.assert_called_once()
            # Verify API client was updated
            assert mock_context.media_api.user_profile is None
            self.assert_feedback_success_called("Successfully logged out")
    
    def test_auth_menu_logout_cancelled(self, mock_context, basic_state, mock_user_profile):
        """Test cancelled logout flow."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, TEST_AUTH_OPTIONS['logout'])
        self.setup_feedback_confirm(False)  # Cancel logout
        
        with self.setup_auth_manager_mock() as mock_auth_manager:
            result = auth(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            # Verify logout confirmation was requested
            self.mock_feedback.confirm.assert_called_once()
            # Verify user profile was not cleared
            mock_auth_manager.clear_user_profile.assert_not_called()
            # Verify API client still has user profile
            assert mock_context.media_api.user_profile == mock_user_profile
            self.assert_feedback_info_called("Logout cancelled")
    
    def test_auth_menu_view_profile(self, mock_context, basic_state, mock_user_profile):
        """Test view profile details."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, TEST_AUTH_OPTIONS['profile'])
        
        result = auth(mock_context, basic_state)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        
        # Verify profile information was displayed
        self.mock_feedback.pause_for_user.assert_called_once()
    
    def test_auth_menu_how_to_get_token(self, mock_unauthenticated_context, basic_state):
        """Test how to get token help."""
        self.setup_selector_choice(mock_unauthenticated_context, TEST_AUTH_OPTIONS['how_to_token'])
        
        with self.setup_webbrowser_mock() as mock_browser:
            result = auth(mock_unauthenticated_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            # Verify browser was opened to AniList developer page
            mock_browser.open.assert_called_once()
            call_args = mock_browser.open.call_args[0]
            assert "anilist.co" in call_args[0].lower()
    
    def test_auth_menu_icons_disabled(self, mock_unauthenticated_context, basic_state):
        """Test menu display with icons disabled."""
        mock_unauthenticated_context.config.general.icons = False
        self.setup_selector_choice(mock_unauthenticated_context, None)
        
        result = auth(mock_unauthenticated_context, basic_state)
        
        self.assert_back_behavior(result)
        # Verify options don't contain emoji icons
        mock_unauthenticated_context.selector.choose.assert_called_once()
        call_args = mock_unauthenticated_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        for choice in choices:
            assert not any(char in choice for char in '🔐👤🔓❓↩️')
    
    def test_auth_menu_display_auth_status_authenticated(self, mock_context, basic_state, mock_user_profile):
        """Test auth status display for authenticated user."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, None)
        
        result = auth(mock_context, basic_state)
        
        self.assert_back_behavior(result)
        # Console should display user information
        assert mock_context.media_api.user_profile == mock_user_profile
    
    def test_auth_menu_display_auth_status_unauthenticated(self, mock_unauthenticated_context, basic_state):
        """Test auth status display for unauthenticated user."""
        self.setup_selector_choice(mock_unauthenticated_context, None)
        
        result = auth(mock_unauthenticated_context, basic_state)
        
        self.assert_back_behavior(result)
        # Should show not authenticated status
        assert mock_unauthenticated_context.media_api.user_profile is None
    
    def test_auth_menu_login_with_whitespace_token(self, mock_unauthenticated_context, basic_state):
        """Test login with token containing whitespace."""
        self.setup_selector_choice(mock_unauthenticated_context, TEST_AUTH_OPTIONS['login'])
        self.setup_selector_input(mock_unauthenticated_context, "  test_token_123  ")  # Token with spaces
        
        # Mock successful authentication
        mock_unauthenticated_context.media_api.authenticate.return_value = Mock()
        
        with self.setup_auth_manager_mock():
            result = auth(mock_unauthenticated_context, basic_state)
            
            self.assert_continue_behavior(result)
            # Verify token was stripped of whitespace
            mock_unauthenticated_context.media_api.authenticate.assert_called_once_with("test_token_123")
    
    def test_auth_menu_authentication_exception_handling(self, mock_unauthenticated_context, basic_state):
        """Test handling of authentication exceptions."""
        self.setup_selector_choice(mock_unauthenticated_context, TEST_AUTH_OPTIONS['login'])
        self.setup_selector_input(mock_unauthenticated_context, "test_token")
        
        # Mock authentication raising an exception
        mock_unauthenticated_context.media_api.authenticate.side_effect = Exception("API Error")
        
        with self.setup_auth_manager_mock():
            result = auth(mock_unauthenticated_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_feedback_error_called("Authentication failed")
    
    def test_auth_menu_save_profile_failure(self, mock_unauthenticated_context, basic_state, mock_user_profile):
        """Test handling of profile save failure after successful auth."""
        self.setup_selector_choice(mock_unauthenticated_context, TEST_AUTH_OPTIONS['login'])
        self.setup_selector_input(mock_unauthenticated_context, "test_token")
        
        # Mock successful authentication but failed save
        mock_unauthenticated_context.media_api.authenticate.return_value = mock_user_profile
        
        with self.setup_auth_manager_mock() as mock_auth_manager:
            mock_auth_manager.save_user_profile.return_value = False  # Save failure
            
            result = auth(mock_unauthenticated_context, basic_state)
            
            self.assert_continue_behavior(result)
            # Should still show success for authentication even if save fails
            self.assert_feedback_success_called("Successfully authenticated")
            # Should show warning about save failure
            self.assert_feedback_warning_called("Failed to save")
    
    @pytest.mark.parametrize("user_input", ["", "   ", "\t", "\n"])
    def test_auth_menu_various_empty_tokens(self, mock_unauthenticated_context, basic_state, user_input):
        """Test various forms of empty token input."""
        self.setup_selector_choice(mock_unauthenticated_context, TEST_AUTH_OPTIONS['login'])
        self.setup_selector_input(mock_unauthenticated_context, user_input)
        
        result = auth(mock_unauthenticated_context, basic_state)
        
        self.assert_continue_behavior(result)
        # Should not attempt authentication with empty/whitespace-only tokens
        mock_unauthenticated_context.media_api.authenticate.assert_not_called()
        self.assert_feedback_warning_called("Token cannot be empty")
