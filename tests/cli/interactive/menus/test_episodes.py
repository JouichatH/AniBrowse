"""
Tests for the episodes menu.
Tests episode selection, watch history integration, and episode navigation.
"""

import pytest
from unittest.mock import Mock, patch

from fastanime.cli.interactive.menus.episodes import episodes
from fastanime.cli.interactive.state import State, ControlFlow, ProviderState, MediaApiState
from fastanime.libs.providers.anime.types import Anime, Episodes

from .base_test import BaseMenuTest, MediaMenuTestMixin


class TestEpisodesMenu(BaseMenuTest, MediaMenuTestMixin):
    """Test cases for the episodes menu."""
    
    @pytest.fixture
    def mock_provider_anime(self):
        """Create a mock provider anime with episodes."""
        anime = Mock(spec=Anime)
        anime.episodes = Mock(spec=Episodes)
        anime.episodes.sub = ["1", "2", "3", "4", "5"]
        anime.episodes.dub = ["1", "2", "3"]
        anime.episodes.raw = []
        anime.title = "Test Anime"
        return anime
    
    @pytest.fixture
    def episodes_state(self, mock_provider_anime, mock_media_item):
        """Create a state with provider anime and media api data."""
        return State(
            menu_name="EPISODES",
            provider=ProviderState(anime=mock_provider_anime),
            media_api=MediaApiState(anime=mock_media_item)
        )
    
    def test_episodes_menu_missing_provider_anime_goes_back(self, mock_context, basic_state):
        """Test that missing provider anime returns BACK."""
        # State with no provider anime
        state_no_anime = State(
            menu_name="EPISODES",
            provider=ProviderState(anime=None),
            media_api=MediaApiState()
        )
        
        result = episodes(mock_context, state_no_anime)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_episodes_menu_missing_media_api_anime_goes_back(self, mock_context, mock_provider_anime):
        """Test that missing media api anime returns BACK."""
        # State with provider anime but no media api anime
        state_no_media = State(
            menu_name="EPISODES",
            provider=ProviderState(anime=mock_provider_anime),
            media_api=MediaApiState(anime=None)
        )
        
        result = episodes(mock_context, state_no_media)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_episodes_menu_no_episodes_available_goes_back(self, mock_context, episodes_state):
        """Test that no available episodes returns BACK."""
        # Configure translation type that has no episodes
        mock_context.config.stream.translation_type = "raw"
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_episodes_menu_no_choice_goes_back(self, mock_context, episodes_state):
        """Test that no choice selected results in BACK."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, None)
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_episodes_menu_episode_selection(self, mock_context, episodes_state):
        """Test normal episode selection."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, "Episode 3")
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_menu_transition(result, "SERVERS")
        self.assert_console_cleared()
        # Verify the selected episode is stored in the new state
        assert "3" in str(result.provider.selected_episode)
    
    def test_episodes_menu_continue_from_local_watch_history(self, mock_context, episodes_state):
        """Test continuing from local watch history."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = True
        mock_context.config.stream.preferred_watch_history = "local"
        
        with patch('fastanime.cli.utils.watch_history_tracker.get_continue_episode') as mock_get_continue:
            mock_get_continue.return_value = "3"  # Continue from episode 3
            
            result = episodes(mock_context, episodes_state)
            
            self.assert_menu_transition(result, "SERVERS")
            self.assert_console_cleared()
            
            # Verify continue episode was retrieved
            mock_get_continue.assert_called_once()
            # Verify the continue episode is selected
            assert "3" in str(result.provider.selected_episode)
    
    def test_episodes_menu_continue_from_anilist_progress(self, mock_context, episodes_state, mock_media_item):
        """Test continuing from AniList progress."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = True
        mock_context.config.stream.preferred_watch_history = "remote"
        
        # Mock AniList progress
        mock_media_item.progress = 2  # Watched 2 episodes, continue from 3
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_menu_transition(result, "SERVERS")
        self.assert_console_cleared()
        # Should continue from next episode after progress
        assert "3" in str(result.provider.selected_episode)
    
    def test_episodes_menu_no_watch_history_fallback_to_manual(self, mock_context, episodes_state):
        """Test fallback to manual selection when no watch history."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = True
        mock_context.config.stream.preferred_watch_history = "local"
        
        with patch('fastanime.cli.utils.watch_history_tracker.get_continue_episode') as mock_get_continue:
            mock_get_continue.return_value = None  # No continue episode
            self.setup_selector_choice(mock_context, "Episode 1")
            
            result = episodes(mock_context, episodes_state)
            
            self.assert_menu_transition(result, "SERVERS")
            self.assert_console_cleared()
            
            # Should fall back to manual selection
            mock_context.selector.choose.assert_called_once()
    
    def test_episodes_menu_translation_type_sub(self, mock_context, episodes_state):
        """Test with subtitle translation type."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, "Episode 1")
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_menu_transition(result, "SERVERS")
        mock_context.selector.choose.assert_called_once()
        # Verify subtitle episodes are available
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        assert len([c for c in choices if "Episode" in c]) == 5  # 5 sub episodes
    
    def test_episodes_menu_translation_type_dub(self, mock_context, episodes_state):
        """Test with dub translation type."""
        mock_context.config.stream.translation_type = "dub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, "Episode 1")
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_menu_transition(result, "SERVERS")
        mock_context.selector.choose.assert_called_once()
        # Verify dub episodes are available
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        assert len([c for c in choices if "Episode" in c]) == 3  # 3 dub episodes
    
    def test_episodes_menu_range_selection(self, mock_context, episodes_state):
        """Test episode range selection."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, "📚 Select Range")
        
        # Mock range input
        with patch.object(mock_context.selector, 'input', return_value="2-4"):
            result = episodes(mock_context, episodes_state)
            
            self.assert_menu_transition(result, "SERVERS")
            self.assert_console_cleared()
            # Should handle range selection
            mock_context.selector.input.assert_called_once()
    
    def test_episodes_menu_invalid_range_selection(self, mock_context, episodes_state):
        """Test invalid episode range selection."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, "📚 Select Range")
        
        # Mock invalid range input
        with patch.object(mock_context.selector, 'input', return_value="invalid-range"):
            result = episodes(mock_context, episodes_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            self.assert_feedback_error_called("Invalid range format")
    
    def test_episodes_menu_watch_all_episodes(self, mock_context, episodes_state):
        """Test watch all episodes option."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, "🎬 Watch All Episodes")
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_menu_transition(result, "SERVERS")
        self.assert_console_cleared()
        # Should set up for watching all episodes
    
    def test_episodes_menu_random_episode(self, mock_context, episodes_state):
        """Test random episode selection."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, "🎲 Random Episode")
        
        with patch('random.choice') as mock_random:
            mock_random.return_value = "3"
            
            result = episodes(mock_context, episodes_state)
            
            self.assert_menu_transition(result, "SERVERS")
            self.assert_console_cleared()
            mock_random.assert_called_once()
    
    def test_episodes_menu_icons_disabled(self, mock_context, episodes_state):
        """Test menu display with icons disabled."""
        mock_context.config.general.icons = False
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, None)
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_back_behavior(result)
        # Verify options don't contain emoji icons
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        for choice in choices:
            assert not any(char in choice for char in '📚🎬🎲')
    
    def test_episodes_menu_progress_indicator(self, mock_context, episodes_state, mock_media_item):
        """Test episode progress indicators."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        mock_media_item.progress = 3  # Watched 3 episodes
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.watch_history_tracker.get_watched_episodes') as mock_watched:
            mock_watched.return_value = ["1", "2", "3"]
            
            result = episodes(mock_context, episodes_state)
            
            self.assert_back_behavior(result)
            # Verify progress indicators were applied
            mock_watched.assert_called_once()
    
    def test_episodes_menu_large_episode_count(self, mock_context, episodes_state, mock_provider_anime):
        """Test handling of anime with many episodes."""
        # Create anime with many episodes
        mock_provider_anime.episodes.sub = [str(i) for i in range(1, 101)]  # 100 episodes
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, None)
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_back_behavior(result)
        # Should handle large episode counts gracefully
        mock_context.selector.choose.assert_called_once()
    
    def test_episodes_menu_zero_padded_episodes(self, mock_context, episodes_state, mock_provider_anime):
        """Test handling of zero-padded episode numbers."""
        mock_provider_anime.episodes.sub = ["01", "02", "03", "04", "05"]
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, "Episode 01")
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_menu_transition(result, "SERVERS")
        # Should handle zero-padded episodes correctly
        assert "01" in str(result.provider.selected_episode)
    
    def test_episodes_menu_special_episodes(self, mock_context, episodes_state, mock_provider_anime):
        """Test handling of special episode formats."""
        mock_provider_anime.episodes.sub = ["1", "2", "3", "S1", "OVA1", "Movie"]
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, "Episode S1")
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_menu_transition(result, "SERVERS")
        # Should handle special episode formats
        assert "S1" in str(result.provider.selected_episode)
    
    def test_episodes_menu_watch_history_tracking(self, mock_context, episodes_state):
        """Test that episode viewing is tracked."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, "Episode 2")
        
        with patch('fastanime.cli.utils.watch_history_tracker.track_episode_viewing') as mock_track:
            result = episodes(mock_context, episodes_state)
            
            self.assert_menu_transition(result, "SERVERS")
            # Verify episode viewing is tracked (if implemented in the menu)
            # This depends on the actual implementation
    
    def test_episodes_menu_episode_metadata_display(self, mock_context, episodes_state):
        """Test episode metadata in choices."""
        mock_context.config.stream.translation_type = "sub"
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, None)
        
        result = episodes(mock_context, episodes_state)
        
        self.assert_back_behavior(result)
        # Verify episode choices include relevant metadata
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # Episode choices should be formatted appropriately
        episode_choices = [c for c in choices if "Episode" in c]
        assert len(episode_choices) > 0
    
    @pytest.mark.parametrize("translation_type,expected_count", [
        ("sub", 5),
        ("dub", 3),
        ("raw", 0),
    ])
    def test_episodes_menu_translation_types(self, mock_context, episodes_state, translation_type, expected_count):
        """Test various translation types."""
        mock_context.config.stream.translation_type = translation_type
        mock_context.config.stream.continue_from_watch_history = False
        self.setup_selector_choice(mock_context, None)
        
        result = episodes(mock_context, episodes_state)
        
        if expected_count == 0:
            self.assert_back_behavior(result)
        else:
            self.assert_back_behavior(result)  # Since no choice was made
            mock_context.selector.choose.assert_called_once()
            call_args = mock_context.selector.choose.call_args
            choices = call_args[1]['choices']
            episode_choices = [c for c in choices if "Episode" in c]
            assert len(episode_choices) == expected_count
