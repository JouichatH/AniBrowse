import importlib.util
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, List

import click

from ...core.config import AppConfig
from ...core.constants import APP_DIR, USER_CONFIG_PATH
from ...libs.api.base import BaseApiClient
from ...libs.players.base import BasePlayer
from ...libs.providers.anime.base import BaseAnimeProvider
from ...libs.selectors.base import BaseSelector
from ..config import ConfigLoader
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

    def _load_context(self, config: AppConfig):
        """Initializes all shared services based on the provided configuration."""
        from ...libs.api.factory import create_api_client
        from ...libs.players import create_player
        from ...libs.providers.anime.provider import create_provider
        from ...libs.selectors import create_selector

        self._context = Context(
            config=config,
            provider=create_provider(config.general.provider),
            selector=create_selector(config),
            player=create_player(config),
            media_api=create_api_client(config.general.api_client, config),
        )
        logger.info("Application context reloaded.")

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
        self._load_context(config)

        if resume_path:
            self.resume(resume_path)
        elif not self._history:
            # Start with the main menu if history is empty
            self._history.append(State(menu_name="MAIN"))

        while self._history:
            current_state = self._history[-1]
            menu_to_run = self._menus.get(current_state.menu_name)

            if not menu_to_run or not self._context:
                logger.error(
                    f"Menu '{current_state.menu_name}' not found or context not loaded."
                )
                break

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
                # A new state was returned, push it to history for the next loop.
                self._history.append(next_step)
            else:
                logger.error(
                    f"Menu '{current_state.menu_name}' returned invalid type: {type(next_step)}"
                )
                break

        click.echo("Exiting interactive session.")

    def save(self, file_path: Path):
        """Serializes the session history to a JSON file."""
        history_dicts = [state.model_dump(mode="json") for state in self._history]
        try:
            file_path.write_text(str(history_dicts))
            logger.info(f"Session saved to {file_path}")
        except IOError as e:
            logger.error(f"Failed to save session: {e}")

    def resume(self, file_path: Path):
        """Loads a session history from a JSON file."""
        if not file_path.exists():
            logger.warning(f"Resume file not found: {file_path}")
            return
        try:
            history_dicts = file_path.read_text()
            self._history = [State.model_validate(d) for d in history_dicts]
            logger.info(f"Session resumed from {file_path}")
        except Exception as e:
            logger.error(f"Failed to resume session: {e}")
            self._history = []  # Reset history on failure

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
