"""
Tests for the episodes menu functionality.
"""

import pytest
from unittest.mock import Mock, patch

from fastanime.cli.interactive.menus.episodes import episodes
from fastanime.cli.interactive.state import ControlFlow, State, MediaApiState, ProviderState
from fastanime.libs.providers.anime.types import Anime, AnimeEpisodes


class TestEpisodesMenu:
    """Test cases for the episodes menu."""

    def test_episodes_menu_missing_anime_data(self, mock_context, empty_state):
        """Test episodes menu with missing anime data."""
        # State without provider or media API anime
        result = episodes(mock_context, empty_state)
        
        # Should go back when anime data is missing
        assert result == ControlFlow.BACK

    def test_episodes_menu_missing_provider_anime(self, mock_context, state_with_media_api):
        """Test episodes menu with missing provider anime."""
        result = episodes(mock_context, state_with_media_api)
        
        # Should go back when provider anime is missing
        assert result == ControlFlow.BACK

    def test_episodes_menu_missing_media_api_anime(self, mock_context, state_with_provider):
        """Test episodes menu with missing media API anime."""
        result = episodes(mock_context, state_with_provider)
        
        # Should go back when media API anime is missing
        assert result == ControlFlow.BACK

    def test_episodes_menu_no_episodes_available(self, mock_context, full_state):
        """Test episodes menu when no episodes are available for translation type."""
        # Mock provider anime with no sub episodes
        provider_anime = Anime(
            name="Test Anime",
            url="https://example.com/anime",
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=AnimeEpisodes(sub=[], dub=["1", "2", "3"])  # No sub episodes
        )
        
        state_no_sub = State(
            menu_name="EPISODES",
            media_api=full_state.media_api,
            provider=ProviderState(anime=provider_anime)
        )
        
        # Config set to sub but no sub episodes available
        mock_context.config.stream.translation_type = "sub"
        
        result = episodes(mock_context, state_no_sub)
        
        # Should go back when no episodes available for translation type
        assert result == ControlFlow.BACK

    def test_episodes_menu_continue_from_local_history(self, mock_context, full_state):
        """Test episodes menu with local watch history continuation."""
        # Setup provider anime with episodes
        provider_anime = Anime(
            name="Test Anime",
            url="https://example.com/anime",
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=Episodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
        )
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=full_state.media_api,
            provider=ProviderState(anime=provider_anime)
        )
        
        # Enable continue from watch history with local preference
        mock_context.config.stream.continue_from_watch_history = True
        mock_context.config.stream.preferred_watch_history = "local"
        
        with patch('fastanime.cli.interactive.menus.episodes.get_continue_episode') as mock_continue:
            mock_continue.return_value = "2"  # Continue from episode 2
            
            with patch('fastanime.cli.interactive.menus.episodes.click.echo'):
                result = episodes(mock_context, state_with_episodes)
                
                # Should transition to SERVERS state with the continue episode
                assert isinstance(result, State)
                assert result.menu_name == "SERVERS"
                assert result.provider.episode_number == "2"

    def test_episodes_menu_continue_from_anilist_progress(self, mock_context, full_state):
        """Test episodes menu with AniList progress continuation."""
        # Setup provider anime with episodes
        provider_anime = Anime(
            name="Test Anime",
            url="https://example.com/anime",
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=Episodes(sub=["1", "2", "3", "4", "5"], dub=["1", "2", "3", "4", "5"])
        )
        
        # Setup media API anime with progress
        media_anime = full_state.media_api.anime
        media_anime.progress = 3  # Watched 3 episodes
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=MediaApiState(anime=media_anime),
            provider=ProviderState(anime=provider_anime)
        )
        
        # Enable continue from watch history with remote preference
        mock_context.config.stream.continue_from_watch_history = True
        mock_context.config.stream.preferred_watch_history = "remote"
        
        with patch('fastanime.cli.interactive.menus.episodes.get_continue_episode') as mock_continue:
            mock_continue.return_value = None  # No local history
            
            with patch('fastanime.cli.interactive.menus.episodes.click.echo'):
                result = episodes(mock_context, state_with_episodes)
                
                # Should transition to SERVERS state with next episode (4)
                assert isinstance(result, State)
                assert result.menu_name == "SERVERS"
                assert result.provider.episode_number == "4"

    def test_episodes_menu_manual_selection(self, mock_context, full_state):
        """Test episodes menu with manual episode selection."""
        # Setup provider anime with episodes
        provider_anime = Anime(
            name="Test Anime",
            url="https://example.com/anime",
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=Episodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
        )
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=full_state.media_api,
            provider=ProviderState(anime=provider_anime)
        )
        
        # Disable continue from watch history
        mock_context.config.stream.continue_from_watch_history = False
        
        # Mock user selection
        mock_context.selector.choose.return_value = "Episode 2"
        
        with patch('fastanime.cli.interactive.menus.episodes._format_episode_choice') as mock_format:
            mock_format.side_effect = lambda ep, _: f"Episode {ep}"
            
            result = episodes(mock_context, state_with_episodes)
            
            # Should transition to SERVERS state with selected episode
            assert isinstance(result, State)
            assert result.menu_name == "SERVERS"
            assert result.provider.episode_number == "2"

    def test_episodes_menu_no_selection_made(self, mock_context, full_state):
        """Test episodes menu when no selection is made."""
        # Setup provider anime with episodes
        provider_anime = Anime(
            name="Test Anime",
            url="https://example.com/anime",
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=Episodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
        )
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=full_state.media_api,
            provider=ProviderState(anime=provider_anime)
        )
        
        # Disable continue from watch history
        mock_context.config.stream.continue_from_watch_history = False
        
        # Mock no selection
        mock_context.selector.choose.return_value = None
        
        result = episodes(mock_context, state_with_episodes)
        
        # Should go back when no selection is made
        assert result == ControlFlow.BACK

    def test_episodes_menu_back_selection(self, mock_context, full_state):
        """Test episodes menu back selection."""
        # Setup provider anime with episodes
        provider_anime = Anime(
            name="Test Anime",
            url="https://example.com/anime",
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=Episodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
        )
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=full_state.media_api,
            provider=ProviderState(anime=provider_anime)
        )
        
        # Disable continue from watch history
        mock_context.config.stream.continue_from_watch_history = False
        
        # Mock back selection
        mock_context.selector.choose.return_value = "Back"
        
        result = episodes(mock_context, state_with_episodes)
        
        # Should go back
        assert result == ControlFlow.BACK

    def test_episodes_menu_invalid_episode_selection(self, mock_context, full_state):
        """Test episodes menu with invalid episode selection."""
        # Setup provider anime with episodes
        provider_anime = Anime(
            name="Test Anime",
            url="https://example.com/anime",
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=Episodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
        )
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=full_state.media_api,
            provider=ProviderState(anime=provider_anime)
        )
        
        # Disable continue from watch history
        mock_context.config.stream.continue_from_watch_history = False
        
        # Mock invalid selection (not in episode map)
        mock_context.selector.choose.return_value = "Invalid Episode"
        
        with patch('fastanime.cli.interactive.menus.episodes._format_episode_choice') as mock_format:
            mock_format.side_effect = lambda ep, _: f"Episode {ep}"
            
            result = episodes(mock_context, state_with_episodes)
            
            # Should go back for invalid selection
            assert result == ControlFlow.BACK

    def test_episodes_menu_dub_translation_type(self, mock_context, full_state):
        """Test episodes menu with dub translation type."""
        # Setup provider anime with both sub and dub episodes
        provider_anime = Anime(
            name="Test Anime",
            url="https://example.com/anime",
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=Episodes(sub=["1", "2", "3"], dub=["1", "2"])  # Only 2 dub episodes
        )
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=full_state.media_api,
            provider=ProviderState(anime=provider_anime)
        )
        
        # Set translation type to dub
        mock_context.config.stream.translation_type = "dub"
        mock_context.config.stream.continue_from_watch_history = False
        
        # Mock user selection
        mock_context.selector.choose.return_value = "Episode 1"
        
        with patch('fastanime.cli.interactive.menus.episodes._format_episode_choice') as mock_format:
            mock_format.side_effect = lambda ep, _: f"Episode {ep}"
            
            result = episodes(mock_context, state_with_episodes)
            
            # Should use dub episodes and transition to SERVERS
            assert isinstance(result, State)
            assert result.menu_name == "SERVERS"
            assert result.provider.episode_number == "1"
            
            # Verify that dub episodes were used (only 2 available)
            mock_context.selector.choose.assert_called_once()
            call_args = mock_context.selector.choose.call_args
            choices = call_args[1]['choices']
            episode_choices = [choice for choice in choices if choice.startswith("Episode")]
            assert len(episode_choices) == 2  # Only 2 dub episodes

    def test_episodes_menu_track_episode_viewing(self, mock_context, full_state):
        """Test that episode viewing is tracked when selected."""
        # Setup provider anime with episodes
        provider_anime = Anime(
            name="Test Anime",
            url="https://example.com/anime",
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=Episodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
        )
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=full_state.media_api,
            provider=ProviderState(anime=provider_anime)
        )
        
        # Use manual selection
        mock_context.config.stream.continue_from_watch_history = False
        mock_context.selector.choose.return_value = "Episode 2"
        
        with patch('fastanime.cli.interactive.menus.episodes._format_episode_choice') as mock_format:
            mock_format.side_effect = lambda ep, _: f"Episode {ep}"
            
            with patch('fastanime.cli.interactive.menus.episodes.track_episode_viewing') as mock_track:
                result = episodes(mock_context, state_with_episodes)
                
                # Should track episode viewing
                mock_track.assert_called_once()
                
                # Should transition to SERVERS
                assert isinstance(result, State)
                assert result.menu_name == "SERVERS"


class TestEpisodesMenuHelperFunctions:
    """Test the helper functions in episodes menu."""

    def test_format_episode_choice(self, mock_config):
        """Test formatting episode choice for display."""
        from fastanime.cli.interactive.menus.episodes import _format_episode_choice
        
        mock_config.general.icons = True
        
        result = _format_episode_choice("1", mock_config)
        
        assert "Episode 1" in result
        assert "▶️" in result  # Icon should be present

    def test_format_episode_choice_no_icons(self, mock_config):
        """Test formatting episode choice without icons."""
        from fastanime.cli.interactive.menus.episodes import _format_episode_choice
        
        mock_config.general.icons = False
        
        result = _format_episode_choice("1", mock_config)
        
        assert "Episode 1" in result
        assert "▶️" not in result  # Icon should not be present

    def test_get_next_episode_from_progress(self, mock_config):
        """Test getting next episode from AniList progress."""
        from fastanime.cli.interactive.menus.episodes import _get_next_episode_from_progress
        
        # Mock media item with progress
        media_item = Mock()
        media_item.progress = 5  # Watched 5 episodes
        
        available_episodes = ["1", "2", "3", "4", "5", "6", "7", "8"]
        
        result = _get_next_episode_from_progress(media_item, available_episodes)
        
        # Should return episode 6 (next after progress)
        assert result == "6"

    def test_get_next_episode_from_progress_no_progress(self, mock_config):
        """Test getting next episode when no progress is available."""
        from fastanime.cli.interactive.menus.episodes import _get_next_episode_from_progress
        
        # Mock media item with no progress
        media_item = Mock()
        media_item.progress = None
        
        available_episodes = ["1", "2", "3", "4", "5"]
        
        result = _get_next_episode_from_progress(media_item, available_episodes)
        
        # Should return episode 1 when no progress
        assert result == "1"

    def test_get_next_episode_from_progress_beyond_available(self, mock_config):
        """Test getting next episode when progress is beyond available episodes."""
        from fastanime.cli.interactive.menus.episodes import _get_next_episode_from_progress
        
        # Mock media item with progress beyond available episodes
        media_item = Mock()
        media_item.progress = 10  # Progress beyond available episodes
        
        available_episodes = ["1", "2", "3", "4", "5"]
        
        result = _get_next_episode_from_progress(media_item, available_episodes)
        
        # Should return None when progress is beyond available episodes
        assert result is None

    def test_get_next_episode_from_progress_at_end(self, mock_config):
        """Test getting next episode when at the end of available episodes."""
        from fastanime.cli.interactive.menus.episodes import _get_next_episode_from_progress
        
        # Mock media item with progress at the end
        media_item = Mock()
        media_item.progress = 5  # Watched all 5 episodes
        
        available_episodes = ["1", "2", "3", "4", "5"]
        
        result = _get_next_episode_from_progress(media_item, available_episodes)
        
        # Should return None when at the end
        assert result is None
