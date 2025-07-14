"""
Tests for the player controls menu functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import threading

from fastanime.cli.interactive.menus.player_controls import player_controls
from fastanime.cli.interactive.state import ControlFlow, State, MediaApiState, ProviderState
from fastanime.libs.players.types import PlayerResult
from fastanime.libs.providers.anime.types import Server, EpisodeStream
from fastanime.libs.api.types import MediaItem


class TestPlayerControlsMenu:
    """Test cases for the player controls menu."""

    def test_player_controls_menu_missing_data(self, mock_context, empty_state):
        """Test player controls menu with missing data."""
        result = player_controls(mock_context, empty_state)
        
        # Should go back when required data is missing
        assert result == ControlFlow.BACK

    def test_player_controls_menu_successful_playback(self, mock_context, full_state):
        """Test player controls menu after successful playback."""
        # Setup state with player result
        state_with_result = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1",
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        # Mock user choice to go back
        mock_context.selector.choose.return_value = "🔙 Back to Episodes"
        
        result = player_controls(mock_context, state_with_result)
        
        # Should go back to episodes
        assert result == ControlFlow.BACK

    def test_player_controls_menu_playback_failure(self, mock_context, full_state):
        """Test player controls menu after playback failure."""
        # Setup state with failed player result
        state_with_failure = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1",
                last_player_result=PlayerResult(success=False, exit_code=1)
            )
        )
        
        # Mock user choice to retry
        mock_context.selector.choose.return_value = "🔄 Try Different Server"
        
        result = player_controls(mock_context, state_with_failure)
        
        # Should transition back to SERVERS state
        assert isinstance(result, State)
        assert result.menu_name == "SERVERS"

    def test_player_controls_next_episode_available(self, mock_context, full_state):
        """Test next episode option when available."""
        # Mock anime with multiple episodes
        from fastanime.libs.providers.anime.types import Episodes
        provider_anime = full_state.provider.anime
        provider_anime.episodes = Episodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
        
        state_with_next = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=provider_anime,
                episode_number="1",  # Currently on episode 1, so 2 is available
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        # Mock user choice to play next episode
        mock_context.selector.choose.return_value = "▶️ Next Episode (2)"
        
        result = player_controls(mock_context, state_with_next)
        
        # Should transition to SERVERS state with next episode
        assert isinstance(result, State)
        assert result.menu_name == "SERVERS"
        assert result.provider.episode_number == "2"

    def test_player_controls_no_next_episode(self, mock_context, full_state):
        """Test when no next episode is available."""
        # Mock anime with only one episode
        from fastanime.libs.providers.anime.types import Episodes
        provider_anime = full_state.provider.anime
        provider_anime.episodes = Episodes(sub=["1"], dub=["1"])
        
        state_last_episode = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=provider_anime,
                episode_number="1",  # Last episode
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        # Mock back selection since no next episode
        mock_context.selector.choose.return_value = "🔙 Back to Episodes"
        
        result = player_controls(mock_context, state_last_episode)
        
        # Should go back
        assert result == ControlFlow.BACK
        
        # Verify next episode option is not in choices
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        next_episode_options = [choice for choice in choices if "Next Episode" in choice]
        assert len(next_episode_options) == 0

    def test_player_controls_replay_episode(self, mock_context, full_state):
        """Test replaying current episode."""
        state_with_result = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1",
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        # Mock user choice to replay
        mock_context.selector.choose.return_value = "🔄 Replay Episode"
        
        result = player_controls(mock_context, state_with_result)
        
        # Should transition back to SERVERS state with same episode
        assert isinstance(result, State)
        assert result.menu_name == "SERVERS"
        assert result.provider.episode_number == "1"

    def test_player_controls_change_server(self, mock_context, full_state):
        """Test changing server option."""
        state_with_result = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1",
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        # Mock user choice to try different server
        mock_context.selector.choose.return_value = "🔄 Try Different Server"
        
        result = player_controls(mock_context, state_with_result)
        
        # Should transition back to SERVERS state
        assert isinstance(result, State)
        assert result.menu_name == "SERVERS"

    def test_player_controls_mark_as_watched(self, mock_context, full_state):
        """Test marking episode as watched."""
        state_with_result = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1",
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        # Mock authenticated user
        mock_context.media_api.is_authenticated.return_value = True
        
        # Mock user choice to mark as watched
        mock_context.selector.choose.return_value = "✅ Mark as Watched"
        
        with patch('fastanime.cli.interactive.menus.player_controls._update_progress_in_background') as mock_update:
            result = player_controls(mock_context, state_with_result)
            
            # Should update progress in background
            mock_update.assert_called_once()
            
            # Should continue
            assert result == ControlFlow.CONTINUE

    def test_player_controls_not_authenticated_no_mark_option(self, mock_context, full_state):
        """Test that mark as watched option is not shown when not authenticated."""
        state_with_result = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1",
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        # Mock unauthenticated user
        mock_context.media_api.is_authenticated.return_value = False
        mock_context.selector.choose.return_value = "🔙 Back to Episodes"
        
        result = player_controls(mock_context, state_with_result)
        
        # Verify mark as watched option is not in choices
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        mark_options = [choice for choice in choices if "Mark as Watched" in choice]
        assert len(mark_options) == 0

    def test_player_controls_auto_next_enabled(self, mock_context, full_state):
        """Test auto next episode when enabled in config."""
        # Enable auto next in config
        mock_context.config.stream.auto_next = True
        
        # Mock anime with multiple episodes
        from fastanime.libs.providers.anime.types import Episodes
        provider_anime = full_state.provider.anime
        provider_anime.episodes = Episodes(sub=["1", "2", "3"], dub=["1", "2", "3"])
        
        state_with_auto_next = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=provider_anime,
                episode_number="1",
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        result = player_controls(mock_context, state_with_auto_next)
        
        # Should automatically transition to next episode
        assert isinstance(result, State)
        assert result.menu_name == "SERVERS"
        assert result.provider.episode_number == "2"
        
        # Selector should not be called for auto next
        mock_context.selector.choose.assert_not_called()

    def test_player_controls_auto_next_last_episode(self, mock_context, full_state):
        """Test auto next when on last episode."""
        # Enable auto next in config
        mock_context.config.stream.auto_next = True
        
        # Mock anime with only one episode
        from fastanime.libs.providers.anime.types import Episodes
        provider_anime = full_state.provider.anime
        provider_anime.episodes = Episodes(sub=["1"], dub=["1"])
        
        state_last_episode = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=provider_anime,
                episode_number="1",
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        # Mock back selection since auto next can't proceed
        mock_context.selector.choose.return_value = "🔙 Back to Episodes"
        
        result = player_controls(mock_context, state_last_episode)
        
        # Should show menu when auto next can't proceed
        assert result == ControlFlow.BACK

    def test_player_controls_no_choice_made(self, mock_context, full_state):
        """Test player controls when no choice is made."""
        state_with_result = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1",
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        # Mock no selection
        mock_context.selector.choose.return_value = None
        
        result = player_controls(mock_context, state_with_result)
        
        # Should go back when no selection is made
        assert result == ControlFlow.BACK

    def test_player_controls_icons_enabled(self, mock_context, full_state):
        """Test player controls menu with icons enabled."""
        mock_context.config.general.icons = True
        
        state_with_result = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1",
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        mock_context.selector.choose.return_value = "🔙 Back to Episodes"
        
        result = player_controls(mock_context, state_with_result)
        
        # Should work with icons enabled
        assert result == ControlFlow.BACK

    def test_player_controls_icons_disabled(self, mock_context, full_state):
        """Test player controls menu with icons disabled."""
        mock_context.config.general.icons = False
        
        state_with_result = State(
            menu_name="PLAYER_CONTROLS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1",
                last_player_result=PlayerResult(success=True, exit_code=0)
            )
        )
        
        mock_context.selector.choose.return_value = "Back to Episodes"
        
        result = player_controls(mock_context, state_with_result)
        
        # Should work with icons disabled
        assert result == ControlFlow.BACK


class TestPlayerControlsHelperFunctions:
    """Test the helper functions in player controls menu."""

    def test_calculate_completion_valid_times(self):
        """Test calculating completion percentage with valid times."""
        from fastanime.cli.interactive.menus.player_controls import _calculate_completion
        
        # 30 minutes out of 60 minutes = 50%
        result = _calculate_completion("00:30:00", "01:00:00")
        
        assert result == 50.0

    def test_calculate_completion_zero_duration(self):
        """Test calculating completion with zero duration."""
        from fastanime.cli.interactive.menus.player_controls import _calculate_completion
        
        result = _calculate_completion("00:30:00", "00:00:00")
        
        assert result == 0

    def test_calculate_completion_invalid_format(self):
        """Test calculating completion with invalid time format."""
        from fastanime.cli.interactive.menus.player_controls import _calculate_completion
        
        result = _calculate_completion("invalid", "01:00:00")
        
        assert result == 0

    def test_calculate_completion_partial_episode(self):
        """Test calculating completion for partial episode viewing."""
        from fastanime.cli.interactive.menus.player_controls import _calculate_completion
        
        # 15 minutes out of 24 minutes = 62.5%
        result = _calculate_completion("00:15:00", "00:24:00")
        
        assert result == 62.5

    def test_update_progress_in_background_authenticated(self, mock_context):
        """Test updating progress in background when authenticated."""
        from fastanime.cli.interactive.menus.player_controls import _update_progress_in_background
        
        # Mock authenticated user
        mock_context.media_api.user_profile = Mock()
        mock_context.media_api.update_list_entry = Mock()
        
        # Call the function
        _update_progress_in_background(mock_context, 123, 5)
        
        # Give the thread a moment to execute
        import time
        time.sleep(0.1)
        
        # Should call update_list_entry
        mock_context.media_api.update_list_entry.assert_called_once()

    def test_update_progress_in_background_not_authenticated(self, mock_context):
        """Test updating progress in background when not authenticated."""
        from fastanime.cli.interactive.menus.player_controls import _update_progress_in_background
        
        # Mock unauthenticated user
        mock_context.media_api.user_profile = None
        mock_context.media_api.update_list_entry = Mock()
        
        # Call the function
        _update_progress_in_background(mock_context, 123, 5)
        
        # Give the thread a moment to execute
        import time
        time.sleep(0.1)
        
        # Should still call update_list_entry (comment suggests it should)
        mock_context.media_api.update_list_entry.assert_called_once()

    def test_get_next_episode_number(self):
        """Test getting next episode number."""
        from fastanime.cli.interactive.menus.player_controls import _get_next_episode_number
        
        available_episodes = ["1", "2", "3", "4", "5"]
        current_episode = "3"
        
        result = _get_next_episode_number(available_episodes, current_episode)
        
        assert result == "4"

    def test_get_next_episode_number_last_episode(self):
        """Test getting next episode when on last episode."""
        from fastanime.cli.interactive.menus.player_controls import _get_next_episode_number
        
        available_episodes = ["1", "2", "3"]
        current_episode = "3"
        
        result = _get_next_episode_number(available_episodes, current_episode)
        
        assert result is None

    def test_get_next_episode_number_not_found(self):
        """Test getting next episode when current episode not found."""
        from fastanime.cli.interactive.menus.player_controls import _get_next_episode_number
        
        available_episodes = ["1", "2", "3"]
        current_episode = "5"  # Not in the list
        
        result = _get_next_episode_number(available_episodes, current_episode)
        
        assert result is None

    def test_should_show_mark_as_watched_authenticated(self, mock_context):
        """Test should show mark as watched when authenticated."""
        from fastanime.cli.interactive.menus.player_controls import _should_show_mark_as_watched
        
        mock_context.media_api.is_authenticated.return_value = True
        player_result = PlayerResult(success=True, exit_code=0)
        
        result = _should_show_mark_as_watched(mock_context, player_result)
        
        assert result is True

    def test_should_show_mark_as_watched_not_authenticated(self, mock_context):
        """Test should not show mark as watched when not authenticated."""
        from fastanime.cli.interactive.menus.player_controls import _should_show_mark_as_watched
        
        mock_context.media_api.is_authenticated.return_value = False
        player_result = PlayerResult(success=True, exit_code=0)
        
        result = _should_show_mark_as_watched(mock_context, player_result)
        
        assert result is False

    def test_should_show_mark_as_watched_playback_failed(self, mock_context):
        """Test should not show mark as watched when playback failed."""
        from fastanime.cli.interactive.menus.player_controls import _should_show_mark_as_watched
        
        mock_context.media_api.is_authenticated.return_value = True
        player_result = PlayerResult(success=False, exit_code=1)
        
        result = _should_show_mark_as_watched(mock_context, player_result)
        
        assert result is False
