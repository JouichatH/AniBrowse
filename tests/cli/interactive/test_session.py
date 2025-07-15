"""
Tests for the interactive session management.
Tests session lifecycle, state management, and menu loading.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from fastanime.cli.interactive.session import Session, Context, session
from fastanime.cli.interactive.state import State, ControlFlow
from fastanime.core.config import AppConfig

from .base_test import BaseMenuTest


class TestSession(BaseMenuTest):
    """Test cases for the Session class."""
    
    @pytest.fixture
    def session_instance(self):
        """Create a fresh session instance for testing."""
        return Session()
    
    def test_session_initialization(self, session_instance):
        """Test session initialization."""
        assert session_instance._context is None
        assert session_instance._history == []
        assert session_instance._menus == {}
        assert session_instance._auto_save_enabled is True
    
    def test_session_menu_decorator(self, session_instance):
        """Test menu decorator registration."""
        @session_instance.menu
        def test_menu(ctx, state):
            return ControlFlow.EXIT
        
        assert "TEST_MENU" in session_instance._menus
        assert session_instance._menus["TEST_MENU"].name == "TEST_MENU"
        assert session_instance._menus["TEST_MENU"].execute == test_menu
    
    def test_session_load_context(self, session_instance, mock_config):
        """Test context loading with dependencies."""
        with patch('fastanime.libs.api.factory.create_api_client') as mock_api:
            with patch('fastanime.libs.providers.anime.provider.create_provider') as mock_provider:
                with patch('fastanime.libs.selectors.create_selector') as mock_selector:
                    with patch('fastanime.libs.players.create_player') as mock_player:
                        
                        mock_api.return_value = Mock()
                        mock_provider.return_value = Mock()
                        mock_selector.return_value = Mock()
                        mock_player.return_value = Mock()
                        
                        session_instance._load_context(mock_config)
                        
                        assert session_instance._context is not None
                        assert isinstance(session_instance._context, Context)
                        
                        # Verify all dependencies were created
                        mock_api.assert_called_once()
                        mock_provider.assert_called_once()
                        mock_selector.assert_called_once()
                        mock_player.assert_called_once()
    
    def test_session_run_basic_flow(self, session_instance, mock_config):
        """Test basic session run flow."""
        # Register a simple test menu
        @session_instance.menu
        def main(ctx, state):
            return ControlFlow.EXIT
        
        with patch.object(session_instance, '_load_context'):
            with patch.object(session_instance._session_manager, 'has_crash_backup', return_value=False):
                with patch.object(session_instance._session_manager, 'has_auto_save', return_value=False):
                    with patch.object(session_instance._session_manager, 'create_crash_backup'):
                        with patch.object(session_instance._session_manager, 'clear_auto_save'):
                            with patch.object(session_instance._session_manager, 'clear_crash_backup'):
                                
                                session_instance.run(mock_config)
                                
                                # Should have started with MAIN menu
                                assert len(session_instance._history) >= 1
                                assert session_instance._history[0].menu_name == "MAIN"
    
    def test_session_run_with_resume_path(self, session_instance, mock_config):
        """Test session run with resume path."""
        resume_path = Path("/test/session.json")
        mock_history = [State(menu_name="TEST")]
        
        with patch.object(session_instance, '_load_context'):
            with patch.object(session_instance, 'resume', return_value=True):
                with patch.object(session_instance._session_manager, 'create_crash_backup'):
                    with patch.object(session_instance._session_manager, 'clear_auto_save'):
                        with patch.object(session_instance._session_manager, 'clear_crash_backup'):
                            
                            # Mock a simple menu to exit immediately
                            @session_instance.menu
                            def test(ctx, state):
                                return ControlFlow.EXIT
                            
                            session_instance._history = mock_history
                            session_instance.run(mock_config, resume_path)
                            
                            # Verify resume was called
                            session_instance.resume.assert_called_once_with(resume_path, session_instance._load_context)
    
    def test_session_run_with_crash_backup(self, session_instance, mock_config):
        """Test session run with crash backup recovery."""
        mock_history = [State(menu_name="RECOVERED")]
        
        with patch.object(session_instance, '_load_context'):
            with patch.object(session_instance._session_manager, 'has_crash_backup', return_value=True):
                with patch.object(session_instance._session_manager, 'has_auto_save', return_value=False):
                    with patch.object(session_instance._session_manager, 'load_crash_backup', return_value=mock_history):
                        with patch.object(session_instance._session_manager, 'clear_crash_backup'):
                            with patch('fastanime.cli.utils.feedback.create_feedback_manager') as mock_feedback:
                                feedback = Mock()
                                feedback.confirm.return_value = True  # Accept recovery
                                mock_feedback.return_value = feedback
                                
                                # Mock menu to exit
                                @session_instance.menu
                                def recovered(ctx, state):
                                    return ControlFlow.EXIT
                                
                                session_instance.run(mock_config)
                                
                                # Should have recovered history
                                assert session_instance._history == mock_history
    
    def test_session_run_with_auto_save_recovery(self, session_instance, mock_config):
        """Test session run with auto-save recovery."""
        mock_history = [State(menu_name="AUTO_SAVED")]
        
        with patch.object(session_instance, '_load_context'):
            with patch.object(session_instance._session_manager, 'has_crash_backup', return_value=False):
                with patch.object(session_instance._session_manager, 'has_auto_save', return_value=True):
                    with patch.object(session_instance._session_manager, 'load_auto_save', return_value=mock_history):
                        with patch('fastanime.cli.utils.feedback.create_feedback_manager') as mock_feedback:
                            feedback = Mock()
                            feedback.confirm.return_value = True  # Accept recovery
                            mock_feedback.return_value = feedback
                            
                            # Mock menu to exit
                            @session_instance.menu
                            def auto_saved(ctx, state):
                                return ControlFlow.EXIT
                            
                            session_instance.run(mock_config)
                            
                            # Should have recovered history
                            assert session_instance._history == mock_history
    
    def test_session_keyboard_interrupt_handling(self, session_instance, mock_config):
        """Test session keyboard interrupt handling."""
        @session_instance.menu
        def main(ctx, state):
            raise KeyboardInterrupt()
        
        with patch.object(session_instance, '_load_context'):
            with patch.object(session_instance._session_manager, 'has_crash_backup', return_value=False):
                with patch.object(session_instance._session_manager, 'has_auto_save', return_value=False):
                    with patch.object(session_instance._session_manager, 'create_crash_backup'):
                        with patch.object(session_instance._session_manager, 'auto_save_session'):
                            with patch('fastanime.cli.utils.feedback.create_feedback_manager') as mock_feedback:
                                feedback = Mock()
                                mock_feedback.return_value = feedback
                                
                                session_instance.run(mock_config)
                                
                                # Should have saved session on interrupt
                                session_instance._session_manager.auto_save_session.assert_called_once()
    
    def test_session_exception_handling(self, session_instance, mock_config):
        """Test session exception handling."""
        @session_instance.menu
        def main(ctx, state):
            raise Exception("Test error")
        
        with patch.object(session_instance, '_load_context'):
            with patch.object(session_instance._session_manager, 'has_crash_backup', return_value=False):
                with patch.object(session_instance._session_manager, 'has_auto_save', return_value=False):
                    with patch.object(session_instance._session_manager, 'create_crash_backup'):
                        with patch('fastanime.cli.utils.feedback.create_feedback_manager') as mock_feedback:
                            feedback = Mock()
                            mock_feedback.return_value = feedback
                            
                            with pytest.raises(Exception, match="Test error"):
                                session_instance.run(mock_config)
    
    def test_session_save_and_resume(self, session_instance):
        """Test session save and resume functionality."""
        test_path = Path("/test/session.json")
        test_history = [State(menu_name="TEST1"), State(menu_name="TEST2")]
        session_instance._history = test_history
        
        with patch.object(session_instance._session_manager, 'save_session', return_value=True) as mock_save:
            with patch.object(session_instance._session_manager, 'load_session', return_value=test_history) as mock_load:
                
                # Test save
                result = session_instance.save(test_path, "test_session", "Test description")
                assert result is True
                mock_save.assert_called_once()
                
                # Test resume
                session_instance._history = []  # Clear history
                result = session_instance.resume(test_path)
                assert result is True
                assert session_instance._history == test_history
                mock_load.assert_called_once()
    
    def test_session_auto_save_functionality(self, session_instance, mock_config):
        """Test auto-save functionality during session run."""
        call_count = 0
        
        @session_instance.menu
        def main(ctx, state):
            nonlocal call_count
            call_count += 1
            if call_count < 6:  # Trigger auto-save after 5 calls
                return State(menu_name="MAIN")
            return ControlFlow.EXIT
        
        with patch.object(session_instance, '_load_context'):
            with patch.object(session_instance._session_manager, 'has_crash_backup', return_value=False):
                with patch.object(session_instance._session_manager, 'has_auto_save', return_value=False):
                    with patch.object(session_instance._session_manager, 'create_crash_backup'):
                        with patch.object(session_instance._session_manager, 'auto_save_session') as mock_auto_save:
                            with patch.object(session_instance._session_manager, 'clear_auto_save'):
                                with patch.object(session_instance._session_manager, 'clear_crash_backup'):
                                    
                                    session_instance.run(mock_config)
                                    
                                    # Auto-save should have been called (every 5 state changes)
                                    mock_auto_save.assert_called()
    
    def test_session_menu_loading_from_folder(self, session_instance):
        """Test loading menus from folder."""
        test_menus_dir = Path("/test/menus")
        
        with patch('os.listdir', return_value=['menu1.py', 'menu2.py', '__init__.py']):
            with patch('importlib.util.spec_from_file_location') as mock_spec:
                with patch('importlib.util.module_from_spec') as mock_module:
                    
                    # Mock successful module loading
                    spec = Mock()
                    spec.loader = Mock()
                    mock_spec.return_value = spec
                    mock_module.return_value = Mock()
                    
                    session_instance.load_menus_from_folder(test_menus_dir)
                    
                    # Should have attempted to load 2 menu files (excluding __init__.py)
                    assert mock_spec.call_count == 2
                    assert spec.loader.exec_module.call_count == 2
    
    def test_session_menu_loading_error_handling(self, session_instance):
        """Test error handling during menu loading."""
        test_menus_dir = Path("/test/menus")
        
        with patch('os.listdir', return_value=['broken_menu.py']):
            with patch('importlib.util.spec_from_file_location', side_effect=Exception("Import error")):
                
                # Should not raise exception, just log error
                session_instance.load_menus_from_folder(test_menus_dir)
                
                # Menu should not be registered
                assert "BROKEN_MENU" not in session_instance._menus
    
    def test_session_control_flow_handling(self, session_instance, mock_config):
        """Test various control flow scenarios."""
        state_count = 0
        
        @session_instance.menu
        def main(ctx, state):
            nonlocal state_count
            state_count += 1
            if state_count == 1:
                return ControlFlow.BACK  # Should pop state if history > 1
            elif state_count == 2:
                return ControlFlow.CONTINUE  # Should re-run current state
            elif state_count == 3:
                return ControlFlow.RELOAD_CONFIG  # Should trigger config edit
            else:
                return ControlFlow.EXIT
        
        @session_instance.menu
        def other(ctx, state):
            return State(menu_name="MAIN")
        
        with patch.object(session_instance, '_load_context'):
            with patch.object(session_instance, '_edit_config'):
                with patch.object(session_instance._session_manager, 'has_crash_backup', return_value=False):
                    with patch.object(session_instance._session_manager, 'has_auto_save', return_value=False):
                        with patch.object(session_instance._session_manager, 'create_crash_backup'):
                            with patch.object(session_instance._session_manager, 'clear_auto_save'):
                                with patch.object(session_instance._session_manager, 'clear_crash_backup'):
                                    
                                    # Add an initial state to test BACK behavior
                                    session_instance._history = [State(menu_name="OTHER"), State(menu_name="MAIN")]
                                    
                                    session_instance.run(mock_config)
                                    
                                    # Should have called edit config
                                    session_instance._edit_config.assert_called_once()
    
    def test_session_get_stats(self, session_instance):
        """Test session statistics retrieval."""
        session_instance._history = [State(menu_name="MAIN"), State(menu_name="TEST")]
        session_instance._auto_save_enabled = True
        
        with patch.object(session_instance._session_manager, 'has_auto_save', return_value=True):
            with patch.object(session_instance._session_manager, 'has_crash_backup', return_value=False):
                
                stats = session_instance.get_session_stats()
                
                assert stats["current_states"] == 2
                assert stats["current_menu"] == "TEST"
                assert stats["auto_save_enabled"] is True
                assert stats["has_auto_save"] is True
                assert stats["has_crash_backup"] is False
    
    def test_session_manual_backup(self, session_instance):
        """Test manual backup creation."""
        session_instance._history = [State(menu_name="TEST")]
        
        with patch.object(session_instance._session_manager, 'save_session', return_value=True):
            result = session_instance.create_manual_backup("test_backup")
            
            assert result is True
            session_instance._session_manager.save_session.assert_called_once()
    
    def test_session_auto_save_toggle(self, session_instance):
        """Test auto-save enable/disable."""
        # Test enabling
        session_instance.enable_auto_save(True)
        assert session_instance._auto_save_enabled is True
        
        # Test disabling
        session_instance.enable_auto_save(False)
        assert session_instance._auto_save_enabled is False
    
    def test_session_cleanup_old_sessions(self, session_instance):
        """Test cleanup of old sessions."""
        with patch.object(session_instance._session_manager, 'cleanup_old_sessions', return_value=3):
            result = session_instance.cleanup_old_sessions(max_sessions=10)
            
            assert result == 3
            session_instance._session_manager.cleanup_old_sessions.assert_called_once_with(10)
    
    def test_session_list_saved_sessions(self, session_instance):
        """Test listing saved sessions."""
        mock_sessions = [
            {"name": "session1", "created": "2024-01-01"},
            {"name": "session2", "created": "2024-01-02"}
        ]
        
        with patch.object(session_instance._session_manager, 'list_saved_sessions', return_value=mock_sessions):
            result = session_instance.list_saved_sessions()
            
            assert result == mock_sessions
            session_instance._session_manager.list_saved_sessions.assert_called_once()
    
    def test_global_session_instance(self):
        """Test that the global session instance is properly initialized."""
        from fastanime.cli.interactive.session import session
        
        assert isinstance(session, Session)
        assert session._context is None
        assert session._history == []
        assert session._menus == {}
