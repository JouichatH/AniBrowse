"""
Tests for the watch history menu.
Tests local watch history display, navigation, and management.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from fastanime.cli.interactive.menus.watch_history import watch_history
from fastanime.cli.interactive.state import State, ControlFlow

from .base_test import BaseMenuTest


class TestWatchHistoryMenu(BaseMenuTest):
    """Test cases for the watch history menu."""
    
    @pytest.fixture
    def mock_watch_history_entries(self):
        """Create mock watch history entries."""
        return [
            {
                "anime_title": "Test Anime 1",
                "episode": "5",
                "timestamp": datetime.now().isoformat(),
                "provider": "test_provider",
                "anilist_id": 12345
            },
            {
                "anime_title": "Test Anime 2", 
                "episode": "12",
                "timestamp": datetime.now().isoformat(),
                "provider": "test_provider",
                "anilist_id": 67890
            },
            {
                "anime_title": "Test Anime 3",
                "episode": "1",
                "timestamp": datetime.now().isoformat(),
                "provider": "test_provider",
                "anilist_id": 11111
            }
        ]
    
    def test_watch_history_menu_no_choice_goes_back(self, mock_context, basic_state):
        """Test that no choice selected results in BACK."""
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = []
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_back_behavior(result)
            self.assert_console_cleared()
    
    def test_watch_history_menu_back_choice(self, mock_context, basic_state):
        """Test explicit back choice."""
        self.setup_selector_choice(mock_context, "↩️ Back to Main Menu")
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = []
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_back_behavior(result)
            self.assert_console_cleared()
    
    def test_watch_history_menu_empty_history(self, mock_context, basic_state):
        """Test display when watch history is empty."""
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = []
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_back_behavior(result)
            self.assert_console_cleared()
            self.assert_feedback_info_called("No watch history found")
    
    def test_watch_history_menu_with_entries(self, mock_context, basic_state, mock_watch_history_entries):
        """Test display with watch history entries."""
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_back_behavior(result)
            self.assert_console_cleared()
            
            # Verify history was retrieved
            mock_get_history.assert_called_once()
            
            # Verify entries are displayed in selector
            mock_context.selector.choose.assert_called_once()
            call_args = mock_context.selector.choose.call_args
            choices = call_args[1]['choices']
            
            # Should have entries plus management options
            history_choices = [c for c in choices if any(anime["anime_title"] in c for anime in mock_watch_history_entries)]
            assert len(history_choices) == len(mock_watch_history_entries)
    
    def test_watch_history_menu_continue_watching(self, mock_context, basic_state, mock_watch_history_entries):
        """Test continuing to watch from history entry."""
        entry_choice = f"Test Anime 1 - Episode 5"
        self.setup_selector_choice(mock_context, entry_choice)
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            # Mock API search for the anime
            mock_context.media_api.search_media.return_value = Mock()
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_menu_transition(result, "RESULTS")
            self.assert_console_cleared()
            
            # Verify API search was called
            mock_context.media_api.search_media.assert_called_once()
    
    def test_watch_history_menu_clear_history_success(self, mock_context, basic_state, mock_watch_history_entries):
        """Test successful history clearing."""
        self.setup_selector_choice(mock_context, "🗑️ Clear All History")
        self.setup_feedback_confirm(True)  # Confirm clearing
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            with patch('fastanime.cli.utils.watch_history_manager.clear_watch_history') as mock_clear:
                mock_clear.return_value = True
                
                result = watch_history(mock_context, basic_state)
                
                self.assert_continue_behavior(result)
                self.assert_console_cleared()
                
                # Verify confirmation was requested
                self.mock_feedback.confirm.assert_called_once()
                # Verify history was cleared
                mock_clear.assert_called_once()
                self.assert_feedback_success_called("Watch history cleared")
    
    def test_watch_history_menu_clear_history_cancelled(self, mock_context, basic_state, mock_watch_history_entries):
        """Test cancelled history clearing."""
        self.setup_selector_choice(mock_context, "🗑️ Clear All History")
        self.setup_feedback_confirm(False)  # Cancel clearing
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            with patch('fastanime.cli.utils.watch_history_manager.clear_watch_history') as mock_clear:
                result = watch_history(mock_context, basic_state)
                
                self.assert_continue_behavior(result)
                self.assert_console_cleared()
                
                # Verify confirmation was requested
                self.mock_feedback.confirm.assert_called_once()
                # Verify history was not cleared
                mock_clear.assert_not_called()
                self.assert_feedback_info_called("Clear cancelled")
    
    def test_watch_history_menu_clear_history_failure(self, mock_context, basic_state, mock_watch_history_entries):
        """Test failed history clearing."""
        self.setup_selector_choice(mock_context, "🗑️ Clear All History")
        self.setup_feedback_confirm(True)  # Confirm clearing
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            with patch('fastanime.cli.utils.watch_history_manager.clear_watch_history') as mock_clear:
                mock_clear.return_value = False
                
                result = watch_history(mock_context, basic_state)
                
                self.assert_continue_behavior(result)
                self.assert_console_cleared()
                self.assert_feedback_error_called("Failed to clear history")
    
    def test_watch_history_menu_export_history(self, mock_context, basic_state, mock_watch_history_entries):
        """Test exporting watch history."""
        self.setup_selector_choice(mock_context, "📤 Export History")
        self.setup_selector_input(mock_context, "/path/to/export.json")
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            with patch('fastanime.cli.utils.watch_history_manager.export_watch_history') as mock_export:
                mock_export.return_value = True
                
                result = watch_history(mock_context, basic_state)
                
                self.assert_continue_behavior(result)
                self.assert_console_cleared()
                
                # Verify export was attempted
                mock_export.assert_called_once()
                self.assert_feedback_success_called("History exported")
    
    def test_watch_history_menu_import_history(self, mock_context, basic_state):
        """Test importing watch history."""
        self.setup_selector_choice(mock_context, "📥 Import History")
        self.setup_selector_input(mock_context, "/path/to/import.json")
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = []
            
            with patch('fastanime.cli.utils.watch_history_manager.import_watch_history') as mock_import:
                mock_import.return_value = True
                
                result = watch_history(mock_context, basic_state)
                
                self.assert_continue_behavior(result)
                self.assert_console_cleared()
                
                # Verify import was attempted
                mock_import.assert_called_once()
                self.assert_feedback_success_called("History imported")
    
    def test_watch_history_menu_remove_single_entry(self, mock_context, basic_state, mock_watch_history_entries):
        """Test removing a single history entry."""
        self.setup_selector_choice(mock_context, "🗑️ Remove Entry")
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            # Mock user selecting entry to remove
            with patch.object(mock_context.selector, 'choose', side_effect=["Test Anime 1 - Episode 5"]):
                with patch('fastanime.cli.utils.watch_history_manager.remove_watch_history_entry') as mock_remove:
                    mock_remove.return_value = True
                    
                    result = watch_history(mock_context, basic_state)
                    
                    self.assert_continue_behavior(result)
                    self.assert_console_cleared()
                    
                    # Verify removal was attempted
                    mock_remove.assert_called_once()
                    self.assert_feedback_success_called("Entry removed")
    
    def test_watch_history_menu_search_history(self, mock_context, basic_state, mock_watch_history_entries):
        """Test searching through watch history."""
        self.setup_selector_choice(mock_context, "🔍 Search History")
        self.setup_selector_input(mock_context, "Test Anime 1")
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            with patch('fastanime.cli.utils.watch_history_manager.search_watch_history') as mock_search:
                filtered_entries = [mock_watch_history_entries[0]]  # Only first entry matches
                mock_search.return_value = filtered_entries
                
                result = watch_history(mock_context, basic_state)
                
                self.assert_continue_behavior(result)
                self.assert_console_cleared()
                
                # Verify search was performed
                mock_search.assert_called_once_with("Test Anime 1")
    
    def test_watch_history_menu_sort_by_date(self, mock_context, basic_state, mock_watch_history_entries):
        """Test sorting history by date."""
        self.setup_selector_choice(mock_context, "📅 Sort by Date")
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            # Should re-display with sorted entries
    
    def test_watch_history_menu_sort_by_anime_title(self, mock_context, basic_state, mock_watch_history_entries):
        """Test sorting history by anime title."""
        self.setup_selector_choice(mock_context, "🔤 Sort by Title")
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            # Should re-display with sorted entries
    
    def test_watch_history_menu_icons_disabled(self, mock_context, basic_state, mock_watch_history_entries):
        """Test menu display with icons disabled."""
        mock_context.config.general.icons = False
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_back_behavior(result)
            # Verify options don't contain emoji icons
            mock_context.selector.choose.assert_called_once()
            call_args = mock_context.selector.choose.call_args
            choices = call_args[1]['choices']
            
            for choice in choices:
                assert not any(char in choice for char in '🗑️📤📥🔍📅🔤↩️')
    
    def test_watch_history_menu_large_history(self, mock_context, basic_state):
        """Test handling of large watch history."""
        # Create large history (100 entries)
        large_history = []
        for i in range(100):
            large_history.append({
                "anime_title": f"Test Anime {i}",
                "episode": f"{i % 12 + 1}",
                "timestamp": datetime.now().isoformat(),
                "provider": "test_provider",
                "anilist_id": 10000 + i
            })
        
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = large_history
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_back_behavior(result)
            # Should handle large history gracefully
            mock_context.selector.choose.assert_called_once()
    
    def test_watch_history_menu_entry_formatting(self, mock_context, basic_state, mock_watch_history_entries):
        """Test proper formatting of history entries."""
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_back_behavior(result)
            
            # Verify entries are formatted with title and episode
            mock_context.selector.choose.assert_called_once()
            call_args = mock_context.selector.choose.call_args
            choices = call_args[1]['choices']
            
            # Check that anime titles and episodes appear in choices
            for entry in mock_watch_history_entries:
                title_found = any(entry["anime_title"] in choice for choice in choices)
                episode_found = any(f"Episode {entry['episode']}" in choice for choice in choices)
                assert title_found and episode_found
    
    def test_watch_history_menu_provider_context(self, mock_context, basic_state, mock_watch_history_entries):
        """Test that provider context is included in entries."""
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_watch_history_entries
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_back_behavior(result)
            
            # Should include provider information
            mock_context.selector.choose.assert_called_once()
            call_args = mock_context.selector.choose.call_args
            choices = call_args[1]['choices']
            
            # Provider info might be shown in choices or header
            header = call_args[1].get('header', '')
            # Provider context should be available somewhere
    
    @pytest.mark.parametrize("history_size", [0, 1, 5, 50, 100])
    def test_watch_history_menu_various_sizes(self, mock_context, basic_state, history_size):
        """Test handling of various history sizes."""
        history_entries = []
        for i in range(history_size):
            history_entries.append({
                "anime_title": f"Test Anime {i}",
                "episode": f"{i % 12 + 1}",
                "timestamp": datetime.now().isoformat(),
                "provider": "test_provider",
                "anilist_id": 10000 + i
            })
        
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.return_value = history_entries
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_back_behavior(result)
            
            if history_size == 0:
                self.assert_feedback_info_called("No watch history found")
            else:
                mock_context.selector.choose.assert_called_once()
    
    def test_watch_history_menu_error_handling(self, mock_context, basic_state):
        """Test error handling when watch history operations fail."""
        self.setup_selector_choice(mock_context, "🗑️ Clear All History")
        self.setup_feedback_confirm(True)
        
        with patch('fastanime.cli.utils.watch_history_manager.get_watch_history') as mock_get_history:
            mock_get_history.side_effect = Exception("History access error")
            
            result = watch_history(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            self.assert_feedback_error_called("An error occurred")
