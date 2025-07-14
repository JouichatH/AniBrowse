"""
Tests for the servers menu functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from fastanime.cli.interactive.menus.servers import servers
from fastanime.cli.interactive.state import ControlFlow, State, MediaApiState, ProviderState
from fastanime.libs.providers.anime.types import Anime, Server, StreamLink
from fastanime.libs.players.types import PlayerResult


class TestServersMenu:
    """Test cases for the servers menu."""

    def test_servers_menu_missing_anime_data(self, mock_context, empty_state):
        """Test servers menu with missing anime data."""
        result = servers(mock_context, empty_state)
        
        # Should go back when anime data is missing
        assert result == ControlFlow.BACK

    def test_servers_menu_missing_episode_number(self, mock_context, state_with_provider):
        """Test servers menu with missing episode number."""
        # Create state with anime but no episode number
        state_no_episode = State(
            menu_name="SERVERS",
            provider=ProviderState(anime=state_with_provider.provider.anime)
        )
        
        result = servers(mock_context, state_no_episode)
        
        # Should go back when episode number is missing
        assert result == ControlFlow.BACK

    def test_servers_menu_successful_server_selection(self, mock_context, full_state):
        """Test successful server selection and playback."""
        # Setup state with episode number
        state_with_episode = State(
            menu_name="SERVERS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1"
            )
        )
        
        # Mock server streams
        mock_servers = [
            Server(
                name="Server 1",
                url="https://example.com/server1",
                links=[
                    StreamLink(url="https://example.com/stream1.m3u8", quality=1080, format="m3u8")
                ]
            ),
            Server(
                name="Server 2", 
                url="https://example.com/server2",
                links=[
                    StreamLink(url="https://example.com/stream2.m3u8", quality=720, format="m3u8")
                ]
            )
        ]
        
        # Mock provider episode streams
        mock_context.provider.episode_streams.return_value = iter(mock_servers)
        
        # Mock server selection
        mock_context.selector.choose.return_value = "Server 1"
        
        # Mock successful player result
        mock_context.player.play.return_value = PlayerResult(success=True, exit_code=0)
        
        result = servers(mock_context, state_with_episode)
        
        # Should transition to PLAYER_CONTROLS state
        assert isinstance(result, State)
        assert result.menu_name == "PLAYER_CONTROLS"
        assert result.provider.last_player_result.success == True

    def test_servers_menu_no_servers_available(self, mock_context, full_state):
        """Test servers menu when no servers are available."""
        # Setup state with episode number
        state_with_episode = State(
            menu_name="SERVERS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1"
            )
        )
        
        # Mock empty server streams
        mock_context.provider.episode_streams.return_value = iter([])
        
        result = servers(mock_context, state_with_episode)
        
        # Should go back when no servers are available
        assert result == ControlFlow.BACK

    def test_servers_menu_server_selection_cancelled(self, mock_context, full_state):
        """Test servers menu when server selection is cancelled."""
        # Setup state with episode number
        state_with_episode = State(
            menu_name="SERVERS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1"
            )
        )
        
        # Mock server streams
        mock_servers = [
            Server(
                name="Server 1",
                url="https://example.com/server1",
                links=[StreamLink(url="https://example.com/stream1.m3u8", quality=1080, format="m3u8")]
            )
        ]
        
        mock_context.provider.episode_streams.return_value = iter(mock_servers)
        
        # Mock no selection (cancelled)
        mock_context.selector.choose.return_value = None
        
        result = servers(mock_context, state_with_episode)
        
        # Should go back when selection is cancelled
        assert result == ControlFlow.BACK

    def test_servers_menu_back_selection(self, mock_context, full_state):
        """Test servers menu back selection."""
        # Setup state with episode number
        state_with_episode = State(
            menu_name="SERVERS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1"
            )
        )
        
        # Mock server streams
        mock_servers = [
            Server(
                name="Server 1",
                url="https://example.com/server1",
                links=[StreamLink(url="https://example.com/stream1.m3u8", quality=1080, format="m3u8")]
            )
        ]
        
        mock_context.provider.episode_streams.return_value = iter(mock_servers)
        
        # Mock back selection
        mock_context.selector.choose.return_value = "Back"
        
        result = servers(mock_context, state_with_episode)
        
        # Should go back
        assert result == ControlFlow.BACK

    def test_servers_menu_auto_server_selection(self, mock_context, full_state):
        """Test automatic server selection when configured."""
        # Setup state with episode number
        state_with_episode = State(
            menu_name="SERVERS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1"
            )
        )
        
        # Mock server streams with specific server name
        mock_servers = [
            Server(
                name="TOP",  # Matches config server preference
                url="https://example.com/server1",
                links=[StreamLink(url="https://example.com/stream1.m3u8", quality=1080, format="m3u8")]
            )
        ]
        
        mock_context.provider.episode_streams.return_value = iter(mock_servers)
        mock_context.config.stream.server = "TOP"  # Auto-select TOP server
        
        # Mock successful player result
        mock_context.player.play.return_value = PlayerResult(success=True, exit_code=0)
        
        result = servers(mock_context, state_with_episode)
        
        # Should auto-select and transition to PLAYER_CONTROLS
        assert isinstance(result, State)
        assert result.menu_name == "PLAYER_CONTROLS"
        
        # Selector should not be called for server selection
        mock_context.selector.choose.assert_not_called()

    def test_servers_menu_quality_filtering(self, mock_context, full_state):
        """Test quality filtering for server links."""
        # Setup state with episode number
        state_with_episode = State(
            menu_name="SERVERS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1"
            )
        )
        
        # Mock server with multiple quality links
        mock_servers = [
            Server(
                name="Server 1",
                url="https://example.com/server1",
                links=[
                    StreamLink(url="https://example.com/stream_720.m3u8", quality=720, format="m3u8"),
                    StreamLink(url="https://example.com/stream_1080.m3u8", quality=1080, format="m3u8"),
                    StreamLink(url="https://example.com/stream_480.m3u8", quality=480, format="m3u8")
                ]
            )
        ]
        
        mock_context.provider.episode_streams.return_value = iter(mock_servers)
        mock_context.config.stream.quality = "720"  # Prefer 720p
        
        # Mock server selection
        mock_context.selector.choose.return_value = "Server 1"
        
        # Mock successful player result
        mock_context.player.play.return_value = PlayerResult(success=True, exit_code=0)
        
        result = servers(mock_context, state_with_episode)
        
        # Should use the 720p link based on quality preference
        mock_context.player.play.assert_called_once()
        player_params = mock_context.player.play.call_args[0][0]
        assert "stream_720.m3u8" in player_params.url

    def test_servers_menu_player_failure(self, mock_context, full_state):
        """Test handling player failure."""
        # Setup state with episode number
        state_with_episode = State(
            menu_name="SERVERS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1"
            )
        )
        
        # Mock server streams
        mock_servers = [
            Server(
                name="Server 1",
                url="https://example.com/server1",
                links=[StreamLink(url="https://example.com/stream1.m3u8", quality=1080, format="m3u8")]
            )
        ]
        
        mock_context.provider.episode_streams.return_value = iter(mock_servers)
        mock_context.selector.choose.return_value = "Server 1"
        
        # Mock failed player result
        mock_context.player.play.return_value = PlayerResult(success=False, exit_code=1)
        
        result = servers(mock_context, state_with_episode)
        
        # Should still transition to PLAYER_CONTROLS state with failure result
        assert isinstance(result, State)
        assert result.menu_name == "PLAYER_CONTROLS"
        assert result.provider.last_player_result.success == False

    def test_servers_menu_server_with_no_links(self, mock_context, full_state):
        """Test handling server with no streaming links."""
        # Setup state with episode number
        state_with_episode = State(
            menu_name="SERVERS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1"
            )
        )
        
        # Mock server with no links
        mock_servers = [
            Server(
                name="Server 1",
                url="https://example.com/server1",
                links=[]  # No streaming links
            )
        ]
        
        mock_context.provider.episode_streams.return_value = iter(mock_servers)
        mock_context.selector.choose.return_value = "Server 1"
        
        result = servers(mock_context, state_with_episode)
        
        # Should go back when no links are available
        assert result == ControlFlow.BACK

    def test_servers_menu_episode_streams_exception(self, mock_context, full_state):
        """Test handling exception during episode streams fetch."""
        # Setup state with episode number
        state_with_episode = State(
            menu_name="SERVERS",
            media_api=full_state.media_api,
            provider=ProviderState(
                anime=full_state.provider.anime,
                episode_number="1"
            )
        )
        
        # Mock exception during episode streams fetch
        mock_context.provider.episode_streams.side_effect = Exception("Network error")
        
        result = servers(mock_context, state_with_episode)
        
        # Should go back on exception
        assert result == ControlFlow.BACK


class TestServersMenuHelperFunctions:
    """Test the helper functions in servers menu."""

    def test_filter_by_quality_exact_match(self):
        """Test filtering links by exact quality match."""
        from fastanime.cli.interactive.menus.servers import _filter_by_quality
        
        links = [
            StreamLink(url="https://example.com/480.m3u8", quality=480, format="m3u8"),
            StreamLink(url="https://example.com/720.m3u8", quality=720, format="m3u8"),
            StreamLink(url="https://example.com/1080.m3u8", quality=1080, format="m3u8")
        ]
        
        result = _filter_by_quality(links, "720")
        
        assert result.quality == 720
        assert "720.m3u8" in result.url

    def test_filter_by_quality_no_match(self):
        """Test filtering links when no quality match is found."""
        from fastanime.cli.interactive.menus.servers import _filter_by_quality
        
        links = [
            StreamLink(url="https://example.com/480.m3u8", quality=480, format="m3u8"),
            StreamLink(url="https://example.com/720.m3u8", quality=720, format="m3u8")
        ]
        
        result = _filter_by_quality(links, "1080")  # Quality not available
        
        # Should return first link when no match
        assert result.quality == 480
        assert "480.m3u8" in result.url

    def test_filter_by_quality_empty_links(self):
        """Test filtering with empty links list."""
        from fastanime.cli.interactive.menus.servers import _filter_by_quality
        
        result = _filter_by_quality([], "720")
        
        # Should return None for empty list
        assert result is None

    def test_format_server_choice_with_quality(self, mock_config):
        """Test formatting server choice with quality information."""
        from fastanime.cli.interactive.menus.servers import _format_server_choice
        
        server = Server(
            name="Test Server",
            url="https://example.com/server",
            links=[
                StreamLink(url="https://example.com/720.m3u8", quality=720, format="m3u8"),
                StreamLink(url="https://example.com/1080.m3u8", quality=1080, format="m3u8")
            ]
        )
        
        mock_config.general.icons = True
        
        result = _format_server_choice(server, mock_config)
        
        assert "Test Server" in result
        assert "720p" in result or "1080p" in result  # Should show available qualities

    def test_format_server_choice_no_icons(self, mock_config):
        """Test formatting server choice without icons."""
        from fastanime.cli.interactive.menus.servers import _format_server_choice
        
        server = Server(
            name="Test Server",
            url="https://example.com/server",
            links=[StreamLink(url="https://example.com/720.m3u8", quality=720, format="m3u8")]
        )
        
        mock_config.general.icons = False
        
        result = _format_server_choice(server, mock_config)
        
        assert "Test Server" in result
        assert "🎬" not in result  # No icons should be present

    def test_get_auto_selected_server_match(self):
        """Test getting auto-selected server when match is found."""
        from fastanime.cli.interactive.menus.servers import _get_auto_selected_server
        
        servers = [
            Server(name="Server 1", url="https://example.com/1", links=[]),
            Server(name="TOP", url="https://example.com/top", links=[]),
            Server(name="Server 2", url="https://example.com/2", links=[])
        ]
        
        result = _get_auto_selected_server(servers, "TOP")
        
        assert result.name == "TOP"

    def test_get_auto_selected_server_no_match(self):
        """Test getting auto-selected server when no match is found."""
        from fastanime.cli.interactive.menus.servers import _get_auto_selected_server
        
        servers = [
            Server(name="Server 1", url="https://example.com/1", links=[]),
            Server(name="Server 2", url="https://example.com/2", links=[])
        ]
        
        result = _get_auto_selected_server(servers, "NonExistent")
        
        # Should return first server when no match
        assert result.name == "Server 1"

    def test_get_auto_selected_server_top_preference(self):
        """Test getting auto-selected server with TOP preference."""
        from fastanime.cli.interactive.menus.servers import _get_auto_selected_server
        
        servers = [
            Server(name="Server 1", url="https://example.com/1", links=[]),
            Server(name="Server 2", url="https://example.com/2", links=[])
        ]
        
        result = _get_auto_selected_server(servers, "TOP")
        
        # Should return first server for TOP preference
        assert result.name == "Server 1"
