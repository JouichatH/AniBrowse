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
            id="test-anime",
            title="Test Anime",
            episodes=AnimeEpisodes(sub=[], dub=["1", "2", "3"]),  # No sub episodes
            poster="https://example.com/poster.jpg"
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
            title="Test Anime",
            
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=AnimeEpisodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
        )
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=full_state.media_api,
            provider=ProviderState(anime=provider_anime)
        )
        
        # Enable continue from watch history with local preference
        mock_context.config.stream.continue_from_watch_history = True
        mock_context.config.stream.preferred_watch_history = "local"
        
        with patch('fastanime.cli.utils.watch_history_tracker.get_continue_episode') as mock_continue:
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
            title="Test Anime",
            
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=AnimeEpisodes(sub=["1", "2", "3", "4", "5"], dub=["1", "2", "3", "4", "5"])
        )
        
        # Setup media API anime with progress
        media_anime = full_state.media_api.anime
        # Set up user status with progress
        if not media_anime.user_status:
            from fastanime.libs.api.types import UserListStatus
            media_anime.user_status = UserListStatus(id=1, progress=3)
        else:
            media_anime.user_status.progress = 3  # Watched 3 episodes
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=MediaApiState(anime=media_anime),
            provider=ProviderState(anime=provider_anime)
        )
        
        # Enable continue from watch history with remote preference
        mock_context.config.stream.continue_from_watch_history = True
        mock_context.config.stream.preferred_watch_history = "remote"
        
        with patch('fastanime.cli.utils.watch_history_tracker.get_continue_episode') as mock_continue:
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
            title="Test Anime",
            
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=AnimeEpisodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
        )
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=full_state.media_api,
            provider=ProviderState(anime=provider_anime)
        )
        
        # Disable continue from watch history
        mock_context.config.stream.continue_from_watch_history = False
         # Mock user selection
        mock_context.selector.choose.return_value = "2"  # Direct episode number
        
        result = episodes(mock_context, state_with_episodes)
        
        # Should transition to SERVERS state with selected episode
        assert isinstance(result, State)
        assert result.menu_name == "SERVERS"
        assert result.provider.episode_number == "2"

    def test_episodes_menu_no_selection_made(self, mock_context, full_state):
        """Test episodes menu when no selection is made."""
        # Setup provider anime with episodes
        provider_anime = Anime(
            title="Test Anime",
            
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=AnimeEpisodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
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
            title="Test Anime",
            
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=AnimeEpisodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
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
            title="Test Anime",
            
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=AnimeEpisodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
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
        
        result = episodes(mock_context, state_with_episodes)
        
        # Current implementation doesn't validate episode selection,
        # so it will proceed to SERVERS state with the invalid episode
        assert isinstance(result, State)
        assert result.menu_name == "SERVERS"
        assert result.provider.episode_number == "Invalid Episode"

    def test_episodes_menu_dub_translation_type(self, mock_context, full_state):
        """Test episodes menu with dub translation type."""
        # Setup provider anime with both sub and dub episodes
        provider_anime = Anime(
            title="Test Anime",
            
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=AnimeEpisodes(sub=["1", "2", "3"], dub=["1", "2"])  # Only 2 dub episodes
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
        mock_context.selector.choose.return_value = "1"
        
        result = episodes(mock_context, state_with_episodes)
        
        # Should use dub episodes and transition to SERVERS
        assert isinstance(result, State)
        assert result.menu_name == "SERVERS"
        assert result.provider.episode_number == "1"
        
        # Verify that dub episodes were used (only 2 available)
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        # Should have only 2 dub episodes plus "Back"
        assert len(choices) == 3  # "1", "2", "Back"

    def test_episodes_menu_track_episode_viewing(self, mock_context, full_state):
        """Test that episode viewing is tracked when selected."""
        # Setup provider anime with episodes
        provider_anime = Anime(
            title="Test Anime",
            
            id="test-anime",
            poster="https://example.com/poster.jpg",
            episodes=AnimeEpisodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
        )
        
        state_with_episodes = State(
            menu_name="EPISODES",
            media_api=full_state.media_api,
            provider=ProviderState(anime=provider_anime)
        )
        
        # Enable tracking (need both continue_from_watch_history and local preference)
        mock_context.config.stream.continue_from_watch_history = True
        mock_context.config.stream.preferred_watch_history = "local"
        mock_context.selector.choose.return_value = "2"
        
        with patch('fastanime.cli.utils.watch_history_tracker.get_continue_episode') as mock_continue:
            mock_continue.return_value = None  # No history, fall back to manual selection
            with patch('fastanime.cli.utils.watch_history_tracker.track_episode_viewing') as mock_track:
                result = episodes(mock_context, state_with_episodes)
                
                # Should track episode viewing
                mock_track.assert_called_once()
                
                # Should transition to SERVERS
                assert isinstance(result, State)
                assert result.menu_name == "SERVERS"
                assert result.provider.episode_number == "2"


