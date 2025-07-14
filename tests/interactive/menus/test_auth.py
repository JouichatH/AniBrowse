"""
Tests for the authentication menu functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from fastanime.cli.interactive.menus.auth import auth
from fastanime.cli.interactive.state import ControlFlow, State
from fastanime.libs.api.types import UserProfile


class TestAuthMenu:
    """Test cases for the authentication menu."""

    def test_auth_menu_not_authenticated(self, mock_context, empty_state):
        """Test auth menu when user is not authenticated."""
        # User not authenticated
        mock_context.media_api.user_profile = None
        mock_context.selector.choose.return_value = None
        
        result = auth(mock_context, empty_state)
        
        # Should go back when no choice is made
        assert result == ControlFlow.BACK
        
        # Verify selector was called with login options
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # Should contain login options
        login_options = ["Login to AniList", "How to Get Token", "Back to Main Menu"]
        for option in login_options:
            assert any(option in choice for choice in choices)

    def test_auth_menu_authenticated(self, mock_context, empty_state):
        """Test auth menu when user is authenticated."""
        # User authenticated
        mock_context.media_api.user_profile = UserProfile(
            id=12345,
            name="TestUser",
            avatar="https://example.com/avatar.jpg"
        )
        mock_context.selector.choose.return_value = None
        
        result = auth(mock_context, empty_state)
        
        # Should go back when no choice is made
        assert result == ControlFlow.BACK
        
        # Verify selector was called with authenticated options
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # Should contain authenticated user options
        auth_options = ["View Profile Details", "Logout", "Back to Main Menu"]
        for option in auth_options:
            assert any(option in choice for choice in choices)

    def test_auth_menu_login_selection(self, mock_context, empty_state):
        """Test selecting login from auth menu."""
        mock_context.media_api.user_profile = None
        
        # Setup selector to return login choice
        login_choice = "🔐 Login to AniList"
        mock_context.selector.choose.return_value = login_choice
        
        with patch('fastanime.cli.interactive.menus.auth._handle_login') as mock_login:
            mock_login.return_value = State(menu_name="MAIN")
            
            result = auth(mock_context, empty_state)
            
            # Should call login handler
            mock_login.assert_called_once()
            assert isinstance(result, State)

    def test_auth_menu_logout_selection(self, mock_context, empty_state):
        """Test selecting logout from auth menu."""
        mock_context.media_api.user_profile = UserProfile(
            id=12345,
            name="TestUser", 
            avatar="https://example.com/avatar.jpg"
        )
        
        # Setup selector to return logout choice
        logout_choice = "🔓 Logout"
        mock_context.selector.choose.return_value = logout_choice
        
        with patch('fastanime.cli.interactive.menus.auth._handle_logout') as mock_logout:
            mock_logout.return_value = ControlFlow.CONTINUE
            
            result = auth(mock_context, empty_state)
            
            # Should call logout handler
            mock_logout.assert_called_once()
            assert result == ControlFlow.CONTINUE

    def test_auth_menu_view_profile_selection(self, mock_context, empty_state):
        """Test selecting view profile from auth menu."""
        mock_context.media_api.user_profile = UserProfile(
            id=12345,
            name="TestUser",
            avatar="https://example.com/avatar.jpg"
        )
        
        # Setup selector to return profile choice
        profile_choice = "👤 View Profile Details"
        mock_context.selector.choose.return_value = profile_choice
        
        with patch('fastanime.cli.interactive.menus.auth._display_user_profile_details') as mock_display:
            with patch('fastanime.cli.interactive.menus.auth.create_feedback_manager') as mock_feedback:
                mock_feedback_obj = Mock()
                mock_feedback.return_value = mock_feedback_obj
                
                result = auth(mock_context, empty_state)
                
                # Should display profile details and continue
                mock_display.assert_called_once()
                mock_feedback_obj.pause_for_user.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_auth_menu_token_help_selection(self, mock_context, empty_state):
        """Test selecting token help from auth menu."""
        mock_context.media_api.user_profile = None
        
        # Setup selector to return help choice
        help_choice = "❓ How to Get Token"
        mock_context.selector.choose.return_value = help_choice
        
        with patch('fastanime.cli.interactive.menus.auth._display_token_help') as mock_help:
            with patch('fastanime.cli.interactive.menus.auth.create_feedback_manager') as mock_feedback:
                mock_feedback_obj = Mock()
                mock_feedback.return_value = mock_feedback_obj
                
                result = auth(mock_context, empty_state)
                
                # Should display token help and continue
                mock_help.assert_called_once()
                mock_feedback_obj.pause_for_user.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_auth_menu_back_selection(self, mock_context, empty_state):
        """Test selecting back from auth menu."""
        mock_context.media_api.user_profile = None
        
        # Setup selector to return back choice
        back_choice = "↩️ Back to Main Menu"
        mock_context.selector.choose.return_value = back_choice
        
        result = auth(mock_context, empty_state)
        
        assert result == ControlFlow.BACK

    def test_auth_menu_icons_enabled(self, mock_context, empty_state):
        """Test auth menu with icons enabled."""
        mock_context.config.general.icons = True
        mock_context.media_api.user_profile = None
        mock_context.selector.choose.return_value = None
        
        result = auth(mock_context, empty_state)
        
        # Should work with icons enabled
        assert result == ControlFlow.BACK

    def test_auth_menu_icons_disabled(self, mock_context, empty_state):
        """Test auth menu with icons disabled."""
        mock_context.config.general.icons = False
        mock_context.media_api.user_profile = None
        mock_context.selector.choose.return_value = None
        
        result = auth(mock_context, empty_state)
        
        # Should work with icons disabled
        assert result == ControlFlow.BACK


class TestAuthMenuHelperFunctions:
    """Test the helper functions in auth menu."""

    def test_display_auth_status_authenticated(self, mock_context):
        """Test displaying auth status when authenticated."""
        from fastanime.cli.interactive.menus.auth import _display_auth_status

        console = Mock()
        user_profile = UserProfile(
            id=12345,
            name="TestUser",
            avatar_url="https://example.com/avatar.jpg"
        )

        _display_auth_status(console, user_profile, True)

        # Should print panel with user info
        console.print.assert_called()
        # Check that panel was created and the user's name appears in the content
        call_args = console.print.call_args_list[0][0][0]  # Get the Panel object
        assert "TestUser" in call_args.renderable
        assert "12345" in call_args.renderable

    def test_display_auth_status_not_authenticated(self, mock_context):
        """Test displaying auth status when not authenticated."""
        from fastanime.cli.interactive.menus.auth import _display_auth_status

        console = Mock()

        _display_auth_status(console, None, True)

        # Should print panel with login info
        console.print.assert_called()
        # Check that panel was created with login information
        call_args = console.print.call_args_list[0][0][0]  # Get the Panel object
        assert "Log in to access" in call_args.renderable

    def test_handle_login_success(self, mock_context):
        """Test successful login process."""
        from fastanime.cli.interactive.menus.auth import _handle_login

        auth_manager = Mock()
        feedback = Mock()

        # Mock successful confirmation for browser opening
        feedback.confirm.return_value = True
        
        # Mock token input
        mock_context.selector.ask.return_value = "valid_token"
        
        # Mock successful authentication
        mock_profile = UserProfile(id=123, name="TestUser")
        mock_context.media_api.authenticate.return_value = mock_profile

        with patch('fastanime.cli.interactive.menus.auth.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, mock_profile)
            
            result = _handle_login(mock_context, auth_manager, feedback, True)

            # Should return CONTINUE on success 
            assert result == ControlFlow.CONTINUE

    def test_handle_login_empty_token(self, mock_context):
        """Test login with empty token."""
        from fastanime.cli.interactive.menus.auth import _handle_login

        auth_manager = Mock()
        feedback = Mock()

        # Mock confirmation for browser opening
        feedback.confirm.return_value = True
        
        # Mock empty token input
        mock_context.selector.ask.return_value = ""

        result = _handle_login(mock_context, auth_manager, feedback, True)

        # Should return CONTINUE when no token provided
        assert result == ControlFlow.CONTINUE

    def test_handle_login_failed_auth(self, mock_context):
        """Test login with failed authentication."""
        from fastanime.cli.interactive.menus.auth import _handle_login

        auth_manager = Mock()
        feedback = Mock()

        # Mock successful confirmation for browser opening
        feedback.confirm.return_value = True
        
        # Mock token input
        mock_context.selector.ask.return_value = "invalid_token"
        
        # Mock failed authentication
        mock_context.media_api.authenticate.return_value = None

        with patch('fastanime.cli.interactive.menus.auth.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (False, None)
            
            result = _handle_login(mock_context, auth_manager, feedback, True)

            # Should return CONTINUE on failed auth
            assert result == ControlFlow.CONTINUE

    def test_handle_login_back_selection(self, mock_context):
        """Test handling login with back selection."""
        from fastanime.cli.interactive.menus.auth import _handle_login
        
        auth_manager = Mock()
        feedback = Mock()
        
        # Mock selector to choose back
        mock_context.selector.choose.return_value = "↩️ Back"
        
        result = _handle_login(mock_context, auth_manager, feedback, True)
        
        # Should return CONTINUE (stay in auth menu)
        assert result == ControlFlow.CONTINUE

    def test_handle_logout_success(self, mock_context):
        """Test successful logout."""
        from fastanime.cli.interactive.menus.auth import _handle_logout
        
        auth_manager = Mock()
        feedback = Mock()
        
        # Mock successful logout
        auth_manager.logout.return_value = True
        feedback.confirm.return_value = True
        
        result = _handle_logout(mock_context, auth_manager, feedback, True)
        
        # Should logout and reload context
        auth_manager.logout.assert_called_once()
        assert result == ControlFlow.RELOAD_CONFIG

    def test_handle_logout_cancelled(self, mock_context):
        """Test cancelled logout."""
        from fastanime.cli.interactive.menus.auth import _handle_logout
        
        auth_manager = Mock()
        feedback = Mock()
        
        # Mock cancelled logout
        feedback.confirm.return_value = False
        
        result = _handle_logout(mock_context, auth_manager, feedback, True)
        
        # Should not logout and continue
        auth_manager.logout.assert_not_called()
        assert result == ControlFlow.CONTINUE

    def test_handle_logout_failure(self, mock_context):
        """Test failed logout."""
        from fastanime.cli.interactive.menus.auth import _handle_logout
        
        auth_manager = Mock()
        feedback = Mock()
        
        # Mock failed logout
        feedback.confirm.return_value = True
        
        with patch('fastanime.cli.interactive.menus.auth.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (False, None)
            
            result = _handle_logout(mock_context, auth_manager, feedback, True)
            
            # Should return RELOAD_CONFIG even on failure because execute_with_feedback handles the error
            assert result == ControlFlow.RELOAD_CONFIG

    def test_display_user_profile_details(self, mock_context):
        """Test displaying user profile details."""
        from fastanime.cli.interactive.menus.auth import _display_user_profile_details
        
        console = Mock()
        user_profile = UserProfile(
            id=12345,
            name="TestUser",
            avatar_url="https://example.com/avatar.jpg"
        )
        
        _display_user_profile_details(console, user_profile, True)
        
        # Should print table with user details
        console.print.assert_called()

    def test_display_token_help(self, mock_context):
        """Test displaying token help information."""
        from fastanime.cli.interactive.menus.auth import _display_token_help
        
        console = Mock()
        
        _display_token_help(console, True)
        
        # Should print help information
        console.print.assert_called()
