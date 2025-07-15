import importlib.util
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List

import click

from ...core.config import AppConfig
from ...core.constants import APP_DIR, USER_CONFIG_PATH
from ...libs.api.base import BaseApiClient
from ...libs.players.base import BasePlayer
from ...libs.providers.anime.base import BaseAnimeProvider
from ...libs.selectors.base import BaseSelector
from ..config import ConfigLoader
from ..utils.session.manager import SessionManager
from .state import ControlFlow, State

logger = logging.getLogger(__name__)

# A type alias for the signature all menu functions must follow.
MenuFunction = Callable[["Context", State], "State | ControlFlow"]

MENUS_DIR = APP_DIR / "cli" / "interactive" / "menus"


@dataclass(frozen=True)
class Context:
    """
    A mutable container for long-lived, shared services and configurations.
    This object is passed to every menu state, providing access to essential
    application components like API clients and UI selectors.
    """

    config: AppConfig
    provider: BaseAnimeProvider
    selector: BaseSelector
    player: BasePlayer
    media_api: BaseApiClient


@dataclass(frozen=True)
class Menu:
    """Represents a registered menu, linking a name to an executable function."""

    name: str
    execute: MenuFunction


class Session:
    """
    The orchestrator for the interactive UI state machine.

    This class manages the state history, holds the application context,
    runs the main event loop, and provides the decorator for registering menus.
    """

    def __init__(self):
        self._context: Context | None = None
        self._history: List[State] = []
        self._menus: dict[str, Menu] = {}
        self._session_manager = SessionManager()
        self._auto_save_enabled = True

    def _load_context(self, config: AppConfig):
        """Initializes all shared services based on the provided configuration."""
        from ...libs.api.factory import create_api_client
        from ...libs.players import create_player
        from ...libs.providers.anime.provider import create_provider
        from ...libs.selectors import create_selector

        # Create API client
        media_api = create_api_client(config.general.api_client, config)

        # Attempt to load saved user authentication
        self._load_saved_authentication(media_api)

        self._context = Context(
            config=config,
            provider=create_provider(config.general.provider),
            selector=create_selector(config),
            player=create_player(config),
            media_api=media_api,
        )
        logger.info("Application context reloaded.")

    def _load_saved_authentication(self, media_api):
        """Attempt to load saved user authentication."""
        try:
            from ..auth.manager import AuthManager

            auth_manager = AuthManager()
            user_data = auth_manager.load_user_profile()

            if user_data and user_data.get("token"):
                # Try to authenticate with the saved token
                profile = media_api.authenticate(user_data["token"])
                if profile:
                    logger.info(f"Successfully authenticated as {profile.name}")
                else:
                    logger.warning("Saved authentication token is invalid or expired")
            else:
                logger.debug("No saved authentication found")

        except Exception as e:
            logger.error(f"Failed to load saved authentication: {e}")
            # Continue without authentication rather than failing completely

    def _edit_config(self):
        """Handles the logic for editing the config file and reloading the context."""
        from ..utils.feedback import create_feedback_manager

        feedback = create_feedback_manager(
            True
        )  # Always use icons for session feedback

        # Confirm before opening editor
        if not feedback.confirm("Open configuration file in editor?", default=True):
            return

        try:
            click.edit(filename=str(USER_CONFIG_PATH))

            def reload_config():
                loader = ConfigLoader()
                new_config = loader.load()
                self._load_context(new_config)
                return new_config

            from ..utils.feedback import execute_with_feedback

            success, _ = execute_with_feedback(
                reload_config,
                feedback,
                "reload configuration",
                loading_msg="Reloading configuration",
                success_msg="Configuration reloaded successfully",
                error_msg="Failed to reload configuration",
                show_loading=False,
            )

            if success:
                feedback.pause_for_user("Press Enter to continue")

        except Exception as e:
            feedback.error("Failed to edit configuration", str(e))
            feedback.pause_for_user("Press Enter to continue")

    def run(self, config: AppConfig, resume_path: Path | None = None):
        """
        Starts and manages the main interactive session loop.

        Args:
            config: The initial application configuration.
            resume_path: Optional path to a saved session file to resume from.
        """
        from ..utils.feedback import create_feedback_manager
        
        feedback = create_feedback_manager(True)  # Always use icons for session messages
        
        self._load_context(config)

        # Handle session recovery
        if resume_path:
            self.resume(resume_path, feedback)
        elif self._session_manager.has_crash_backup():
            # Offer to resume from crash backup
            if feedback.confirm(
                "Found a crash backup from a previous session. Would you like to resume?",
                default=True
            ):
                crash_history = self._session_manager.load_crash_backup(feedback)
                if crash_history:
                    self._history = crash_history
                    feedback.info("Session restored from crash backup")
                    # Clear the crash backup after successful recovery
                    self._session_manager.clear_crash_backup()
        elif self._session_manager.has_auto_save():
            # Offer to resume from auto-save
            if feedback.confirm(
                "Found an auto-saved session. Would you like to resume?",
                default=False
            ):
                auto_history = self._session_manager.load_auto_save(feedback)
                if auto_history:
                    self._history = auto_history
                    feedback.info("Session restored from auto-save")

        # Start with main menu if no history
        if not self._history:
            self._history.append(State(menu_name="MAIN"))

        # Create crash backup before starting
        if self._auto_save_enabled:
            self._session_manager.create_crash_backup(self._history)

        try:
            self._run_main_loop()
        except KeyboardInterrupt:
            feedback.warning("Session interrupted by user")
            self._handle_session_exit(feedback, interrupted=True)
        except Exception as e:
            feedback.error("Session crashed unexpectedly", str(e))
            self._handle_session_exit(feedback, crashed=True)
            raise
        else:
            self._handle_session_exit(feedback, normal_exit=True)

    def _run_main_loop(self):
        """Run the main session loop."""
        while self._history:
            current_state = self._history[-1]
            menu_to_run = self._menus.get(current_state.menu_name)

            if not menu_to_run or not self._context:
                logger.error(
                    f"Menu '{current_state.menu_name}' not found or context not loaded."
                )
                break

            # Auto-save periodically (every 5 state changes)
            if self._auto_save_enabled and len(self._history) % 5 == 0:
                self._session_manager.auto_save_session(self._history)

            # Execute the menu function, which returns the next step.
            next_step = menu_to_run.execute(self._context, current_state)

            if isinstance(next_step, ControlFlow):
                # A control command was issued.
                if next_step == ControlFlow.EXIT:
                    break  # Exit the loop
                elif next_step == ControlFlow.BACK:
                    if len(self._history) > 1:
                        self._history.pop()  # Go back one state
                elif next_step == ControlFlow.RELOAD_CONFIG:
                    self._edit_config()
                # For CONTINUE, we do nothing, allowing the loop to re-run the current state.
            elif isinstance(next_step, State):
                # if the state is main menu we should reset the history
                if next_step.menu_name == "MAIN":
                    self._history = [next_step]
                else:
                    # A new state was returned, push it to history for the next loop.
                    self._history.append(next_step)
            else:
                logger.error(
                    f"Menu '{current_state.menu_name}' returned invalid type: {type(next_step)}"
                )
                break

    def _handle_session_exit(self, feedback, normal_exit=False, interrupted=False, crashed=False):
        """Handle session cleanup on exit."""
        if self._auto_save_enabled and self._history:
            if normal_exit:
                # Clear auto-save on normal exit
                self._session_manager.clear_auto_save()
                self._session_manager.clear_crash_backup()
                feedback.info("Session completed normally")
            elif interrupted:
                # Save session on interruption
                self._session_manager.auto_save_session(self._history)
                feedback.info("Session auto-saved due to interruption")
            elif crashed:
                # Keep crash backup on crash
                feedback.error("Session backup maintained for recovery")

        click.echo("Exiting interactive session.")

    def save(self, file_path: Path, session_name: str = None, description: str = None):
        """
        Save session history to a file with comprehensive metadata and error handling.
        
        Args:
            file_path: Path to save the session
            session_name: Optional name for the session
            description: Optional description for the session
        """
        from ..utils.feedback import create_feedback_manager
        
        feedback = create_feedback_manager(True)
        return self._session_manager.save_session(
            self._history, 
            file_path,
            session_name=session_name,
            description=description,
            feedback=feedback
        )

    def resume(self, file_path: Path, feedback=None):
        """
        Load session history from a file with comprehensive error handling.
        
        Args:
            file_path: Path to the session file
            feedback: Optional feedback manager for user notifications
        """
        if not feedback:
            from ..utils.feedback import create_feedback_manager
            feedback = create_feedback_manager(True)
            
        history = self._session_manager.load_session(file_path, feedback)
        if history:
            self._history = history
            return True
        return False

    def list_saved_sessions(self):
        """List all saved sessions with their metadata."""
        return self._session_manager.list_saved_sessions()

    def cleanup_old_sessions(self, max_sessions: int = 10):
        """Clean up old session files, keeping only the most recent ones."""
        return self._session_manager.cleanup_old_sessions(max_sessions)

    def enable_auto_save(self, enabled: bool = True):
        """Enable or disable auto-save functionality."""
        self._auto_save_enabled = enabled

    def get_session_stats(self) -> dict:
        """Get statistics about the current session."""
        return {
            "current_states": len(self._history),
            "current_menu": self._history[-1].menu_name if self._history else None,
            "auto_save_enabled": self._auto_save_enabled,
            "has_auto_save": self._session_manager.has_auto_save(),
            "has_crash_backup": self._session_manager.has_crash_backup()
        }

    def create_manual_backup(self, backup_name: str = None):
        """Create a manual backup of the current session."""
        from ..utils.feedback import create_feedback_manager
        from ...core.constants import APP_DIR
        
        feedback = create_feedback_manager(True)
        backup_name = backup_name or f"manual_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = APP_DIR / "sessions" / f"{backup_name}.json"
        
        return self._session_manager.save_session(
            self._history,
            backup_path,
            session_name=backup_name,
            description="Manual backup created by user",
            feedback=feedback
        )

    @property
    def menu(self) -> Callable[[MenuFunction], MenuFunction]:
        """A decorator to register a function as a menu."""

        def decorator(func: MenuFunction) -> MenuFunction:
            menu_name = func.__name__.upper()
            if menu_name in self._menus:
                logger.warning(f"Menu '{menu_name}' is being redefined.")
            self._menus[menu_name] = Menu(name=menu_name, execute=func)
            return func

        return decorator

    def load_menus_from_folder(self, package_path: Path = MENUS_DIR):
        """
        Dynamically imports all Python modules from a folder to register their menus.

        Args:
            package_path: The filesystem path to the 'menus' package directory.
        """
        package_name = package_path.name
        logger.debug(f"Loading menus from '{package_path}'...")

        for filename in os.listdir(package_path):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]
                full_module_name = (
                    f"fastanime.cli.interactive.{package_name}.{module_name}"
                )
                file_path = package_path / filename

                try:
                    spec = importlib.util.spec_from_file_location(
                        full_module_name, file_path
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        # The act of executing the module runs the @session.menu decorators
                        spec.loader.exec_module(module)
                except Exception as e:
                    logger.error(
                        f"Failed to load menu module '{full_module_name}': {e}"
                    )


# Create a single, global instance of the Session to be imported by menu modules.
session = Session()
