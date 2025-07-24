import importlib.util
import logging
import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Union

import click

from ...core.config import AppConfig
from ...core.constants import APP_DIR, USER_CONFIG_PATH
from ...libs.media_api.base import BaseApiClient
from ...libs.players.base import BasePlayer
from ...libs.providers.anime.base import BaseAnimeProvider
from ...libs.selectors.base import BaseSelector
from ..services.auth import AuthService
from ..services.feedback import FeedbackService
from ..services.registry import MediaRegistryService
from ..services.session import SessionsService
from ..services.watch_history import WatchHistoryService
from .state import InternalDirective, MenuName, State

logger = logging.getLogger(__name__)

# A type alias for the signature all menu functions must follow.

MENUS_DIR = APP_DIR / "cli" / "interactive" / "menus"


@dataclass(frozen=True)
class Services:
    feedback: FeedbackService
    media_registry: MediaRegistryService
    watch_history: WatchHistoryService
    session: SessionsService
    auth: AuthService


@dataclass(frozen=True)
class Context:
    config: AppConfig
    provider: BaseAnimeProvider
    selector: BaseSelector
    player: BasePlayer
    media_api: BaseApiClient
    services: Services


MenuFunction = Callable[[Context, State], Union[State, InternalDirective]]


@dataclass(frozen=True)
class Menu:
    name: MenuName
    execute: MenuFunction


class Session:
    _context: Context
    _history: List[State] = []
    _menus: dict[MenuName, Menu] = {}

    def _load_context(self, config: AppConfig):
        """Initializes all shared services based on the provided configuration."""
        from ...libs.media_api.api import create_api_client
        from ...libs.players import create_player
        from ...libs.providers.anime.provider import create_provider
        from ...libs.selectors import create_selector

        media_registry = MediaRegistryService(
            media_api=config.general.media_api, config=config.media_registry
        )
        auth = AuthService(config.general.media_api)
        services = Services(
            feedback=FeedbackService(config.general.icons),
            media_registry=media_registry,
            watch_history=WatchHistoryService(config, media_registry),
            session=SessionsService(config.sessions),
            auth=auth,
        )

        media_api = create_api_client(config.general.media_api, config)

        if auth_profile := auth.get_auth():
            p = media_api.authenticate(auth_profile.token)
            if p:
                logger.debug(f"Authenticated as {p.name}")
            else:
                logger.warning(f"Failed to authenticate with {auth_profile.token}")
        else:
            logger.debug("Not authenticated")

        self._context = Context(
            config=config,
            provider=create_provider(config.general.provider),
            selector=create_selector(config),
            player=create_player(config),
            media_api=media_api,
            services=services,
        )
        logger.info("Application context reloaded.")

    def _edit_config(self):
        from ..config import ConfigLoader

        click.edit(filename=str(USER_CONFIG_PATH))
        logger.debug("Config changed; Reloading context")
        loader = ConfigLoader()
        config = loader.load()
        self._load_context(config)

    def run(
        self,
        config: AppConfig,
        resume: bool = False,
        history: Optional[List[State]] = None,
    ):
        self._load_context(config)
        if resume:
            if (
                history
                := self._context.services.session.get_most_recent_session_history()
            ):
                self._history = history
            else:
                logger.warning("Failed to continue from history. No sessions found")

        if not self._history:
            self._history.append(State(menu_name=MenuName.MAIN))

        try:
            self._run_main_loop()
        except Exception:
            self._context.services.session.create_crash_backup(self._history)
            raise
        self._context.services.session.save_session(self._history)

    def _run_main_loop(self):
        """Run the main session loop."""
        while self._history:
            current_state = self._history[-1]

            next_step = self._menus[current_state.menu_name].execute(
                self._context, current_state
            )

            if isinstance(next_step, InternalDirective):
                if next_step == InternalDirective.MAIN:
                    self._history = [self._history[0]]
                if next_step == InternalDirective.RELOAD:
                    continue
                elif next_step == InternalDirective.CONFIG_EDIT:
                    self._edit_config()
                elif next_step == InternalDirective.BACK:
                    if len(self._history) > 1:
                        self._history.pop()
                elif next_step == InternalDirective.BACKX2:
                    if len(self._history) > 2:
                        self._history.pop()
                        self._history.pop()
                elif next_step == InternalDirective.BACKX3:
                    if len(self._history) > 3:
                        self._history.pop()
                        self._history.pop()
                        self._history.pop()
                elif next_step == InternalDirective.EXIT:
                    break
            else:
                self._history.append(next_step)

    @property
    def menu(self) -> Callable[[MenuFunction], MenuFunction]:
        """A decorator to register a function as a menu."""

        def decorator(func: MenuFunction) -> MenuFunction:
            menu_name = MenuName(func.__name__.upper())
            if menu_name in self._menus:
                logger.warning(f"Menu '{menu_name}' is being redefined.")
            self._menus[menu_name] = Menu(name=menu_name, execute=func)
            return func

        return decorator

    def load_menus_from_folder(self, package:str):
        package_path = MENUS_DIR / package
        package_name = package_path.name
        logger.debug(f"Loading menus from '{package_path}'...")

        for filename in os.listdir(package_path):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]
                full_module_name = (
                    f"fastanime.cli.interactive.menus.{package_name}.{module_name}"
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
