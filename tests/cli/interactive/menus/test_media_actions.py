"""
Tests for the media actions menu.
Tests anime-specific actions like adding to list, searching providers, etc.
"""

import pytest
from unittest.mock import Mock, patch

from fastanime.cli.interactive.menus.media_actions import media_actions
from fastanime.cli.interactive.state import State, ControlFlow, MediaApiState

from .base_test import BaseMenuTest, MediaMenuTestMixin


class TestMediaActionsMenu(BaseMenuTest, MediaMenuTestMixin):
    """Test cases for the media actions menu."""
    
    def test_media_actions_no_anime_goes_back(self, mock_context, basic_state):
        """Test that missing anime data returns BACK."""
        # State with no anime data
        state_no_anime = State(
            menu_name="MEDIA_ACTIONS",
            media_api=MediaApiState(anime=None)
        )
        
        result = media_actions(mock_context, state_no_anime)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_media_actions_no_choice_goes_back(self, mock_context, state_with_media_data):
        """Test that no choice selected results in BACK."""
        self.setup_selector_choice(mock_context, None)
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_media_actions_back_choice(self, mock_context, state_with_media_data):
        """Test explicit back choice."""
        self.setup_selector_choice(mock_context, "↩️ Back")
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_media_actions_search_providers(self, mock_context, state_with_media_data):
        """Test searching providers for the anime."""
        self.setup_selector_choice(mock_context, "🔍 Search Providers")
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_menu_transition(result, "PROVIDER_SEARCH")
        self.assert_console_cleared()
    
    def test_media_actions_add_to_list_authenticated(self, mock_context, state_with_media_data, mock_user_profile):
        """Test adding anime to list when authenticated."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, "➕ Add to List")
        
        # Mock status selection
        with patch.object(mock_context.selector, 'choose', side_effect=["WATCHING"]):
            mock_context.media_api.update_list_entry.return_value = True
            
            result = media_actions(mock_context, state_with_media_data)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            # Verify list update was attempted
            mock_context.media_api.update_list_entry.assert_called_once()
            self.assert_feedback_success_called("Added to list")
    
    def test_media_actions_add_to_list_unauthenticated(self, mock_unauthenticated_context, state_with_media_data):
        """Test adding anime to list when not authenticated."""
        self.setup_selector_choice(mock_unauthenticated_context, "➕ Add to List")
        
        result = media_actions(mock_unauthenticated_context, state_with_media_data)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        self.assert_feedback_error_called("Authentication required")
    
    def test_media_actions_update_list_entry(self, mock_context, state_with_media_data, mock_user_profile):
        """Test updating existing list entry."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, "✏️ Update List Entry")
        
        # Mock current status and new status selection
        with patch.object(mock_context.selector, 'choose', side_effect=["COMPLETED"]):
            mock_context.media_api.update_list_entry.return_value = True
            
            result = media_actions(mock_context, state_with_media_data)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            # Verify list update was attempted
            mock_context.media_api.update_list_entry.assert_called_once()
            self.assert_feedback_success_called("List entry updated")
    
    def test_media_actions_remove_from_list(self, mock_context, state_with_media_data, mock_user_profile):
        """Test removing anime from list."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, "🗑️ Remove from List")
        self.setup_feedback_confirm(True)  # Confirm removal
        
        mock_context.media_api.delete_list_entry.return_value = True
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        
        # Verify removal was attempted
        mock_context.media_api.delete_list_entry.assert_called_once()
        self.assert_feedback_success_called("Removed from list")
    
    def test_media_actions_remove_from_list_cancelled(self, mock_context, state_with_media_data, mock_user_profile):
        """Test cancelled removal from list."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, "🗑️ Remove from List")
        self.setup_feedback_confirm(False)  # Cancel removal
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        
        # Verify removal was not attempted
        mock_context.media_api.delete_list_entry.assert_not_called()
        self.assert_feedback_info_called("Removal cancelled")
    
    def test_media_actions_view_details(self, mock_context, state_with_media_data):
        """Test viewing anime details."""
        self.setup_selector_choice(mock_context, "📋 View Details")
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        # Should display details and pause for user
        self.mock_feedback.pause_for_user.assert_called_once()
    
    def test_media_actions_view_characters(self, mock_context, state_with_media_data):
        """Test viewing anime characters."""
        self.setup_selector_choice(mock_context, "👥 View Characters")
        
        # Mock character data
        mock_characters = [
            {"name": "Character 1", "role": "MAIN"},
            {"name": "Character 2", "role": "SUPPORTING"}
        ]
        mock_context.media_api.get_anime_characters.return_value = mock_characters
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        
        # Verify characters were fetched
        mock_context.media_api.get_anime_characters.assert_called_once()
        self.mock_feedback.pause_for_user.assert_called_once()
    
    def test_media_actions_view_staff(self, mock_context, state_with_media_data):
        """Test viewing anime staff."""
        self.setup_selector_choice(mock_context, "🎬 View Staff")
        
        # Mock staff data
        mock_staff = [
            {"name": "Director Name", "role": "Director"},
            {"name": "Studio Name", "role": "Studio"}
        ]
        mock_context.media_api.get_anime_staff.return_value = mock_staff
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        
        # Verify staff were fetched
        mock_context.media_api.get_anime_staff.assert_called_once()
        self.mock_feedback.pause_for_user.assert_called_once()
    
    def test_media_actions_view_reviews(self, mock_context, state_with_media_data):
        """Test viewing anime reviews."""
        self.setup_selector_choice(mock_context, "⭐ View Reviews")
        
        # Mock review data
        mock_reviews = [
            {"author": "User1", "rating": 9, "summary": "Great anime!"},
            {"author": "User2", "rating": 7, "summary": "Pretty good."}
        ]
        mock_context.media_api.get_anime_reviews.return_value = mock_reviews
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        
        # Verify reviews were fetched
        mock_context.media_api.get_anime_reviews.assert_called_once()
        self.mock_feedback.pause_for_user.assert_called_once()
    
    def test_media_actions_view_recommendations(self, mock_context, state_with_media_data):
        """Test viewing anime recommendations."""
        self.setup_selector_choice(mock_context, "💡 View Recommendations")
        
        # Mock recommendation data
        mock_recommendations = self.create_mock_media_result(3)
        mock_context.media_api.get_anime_recommendations.return_value = mock_recommendations
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_menu_transition(result, "RESULTS")
        self.assert_console_cleared()
        
        # Verify recommendations were fetched
        mock_context.media_api.get_anime_recommendations.assert_called_once()
    
    def test_media_actions_set_progress(self, mock_context, state_with_media_data, mock_user_profile):
        """Test setting anime progress."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, "📊 Set Progress")
        self.setup_selector_input(mock_context, "5")  # Episode 5
        
        mock_context.media_api.update_list_entry.return_value = True
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        
        # Verify progress update was attempted
        mock_context.media_api.update_list_entry.assert_called_once()
        self.assert_feedback_success_called("Progress updated")
    
    def test_media_actions_set_score(self, mock_context, state_with_media_data, mock_user_profile):
        """Test setting anime score."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, "🌟 Set Score")
        self.setup_selector_input(mock_context, "8")  # Score of 8
        
        mock_context.media_api.update_list_entry.return_value = True
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        
        # Verify score update was attempted
        mock_context.media_api.update_list_entry.assert_called_once()
        self.assert_feedback_success_called("Score updated")
    
    def test_media_actions_open_external_links(self, mock_context, state_with_media_data):
        """Test opening external links."""
        self.setup_selector_choice(mock_context, "🔗 External Links")
        
        # Mock external links submenu
        with patch.object(mock_context.selector, 'choose', side_effect=["AniList Page"]):
            with patch('webbrowser.open') as mock_browser:
                result = media_actions(mock_context, state_with_media_data)
                
                self.assert_continue_behavior(result)
                self.assert_console_cleared()
                
                # Verify browser was opened
                mock_browser.assert_called_once()
    
    def test_media_actions_icons_disabled(self, mock_context, state_with_media_data):
        """Test menu display with icons disabled."""
        mock_context.config.general.icons = False
        self.setup_selector_choice(mock_context, None)
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_back_behavior(result)
        # Verify options don't contain emoji icons
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        for choice in choices:
            assert not any(char in choice for char in '🔍➕✏️🗑️📋👥🎬⭐💡📊🌟🔗↩️')
    
    def test_media_actions_api_failures(self, mock_context, state_with_media_data, mock_user_profile):
        """Test handling of API failures."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, "➕ Add to List")
        
        # Mock API failure
        mock_context.media_api.update_list_entry.return_value = False
        
        with patch.object(mock_context.selector, 'choose', side_effect=["WATCHING"]):
            result = media_actions(mock_context, state_with_media_data)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            self.assert_feedback_error_called("Failed to update list")
    
    def test_media_actions_invalid_input_handling(self, mock_context, state_with_media_data, mock_user_profile):
        """Test handling of invalid user input."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, "📊 Set Progress")
        self.setup_selector_input(mock_context, "invalid")  # Invalid progress
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        self.assert_feedback_error_called("Invalid progress")
    
    @pytest.mark.parametrize("list_status", ["WATCHING", "COMPLETED", "PLANNING", "PAUSED", "DROPPED"])
    def test_media_actions_various_list_statuses(self, mock_context, state_with_media_data, mock_user_profile, list_status):
        """Test adding anime to list with various statuses."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, "➕ Add to List")
        
        with patch.object(mock_context.selector, 'choose', side_effect=[list_status]):
            mock_context.media_api.update_list_entry.return_value = True
            
            result = media_actions(mock_context, state_with_media_data)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            # Verify the status was used
            call_args = mock_context.media_api.update_list_entry.call_args
            assert list_status in str(call_args)
    
    def test_media_actions_anime_details_display(self, mock_context, state_with_media_data, mock_media_item):
        """Test anime details are properly displayed in header."""
        self.setup_selector_choice(mock_context, None)
        
        result = media_actions(mock_context, state_with_media_data)
        
        self.assert_back_behavior(result)
        # Verify anime details appear in header
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        header = call_args[1].get('header', '')
        assert mock_media_item.title in header
    
    def test_media_actions_authentication_status_context(self, mock_unauthenticated_context, state_with_media_data):
        """Test that authentication status affects available options."""
        self.setup_selector_choice(mock_unauthenticated_context, None)
        
        result = media_actions(mock_unauthenticated_context, state_with_media_data)
        
        self.assert_back_behavior(result)
        # Verify authentication-dependent options are handled appropriately
        mock_unauthenticated_context.selector.choose.assert_called_once()
        call_args = mock_unauthenticated_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # List management options should either not appear or show auth prompts
        list_actions = [c for c in choices if any(action in c for action in ["Add to List", "Update List", "Remove from List"])]
        # These should either be absent or handled with auth checks
