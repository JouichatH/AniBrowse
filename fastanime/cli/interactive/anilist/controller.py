from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from .states.base import GoBack, State

if TYPE_CHECKING:
    from ..session import Session

logger = logging.getLogger(__name__)


class InteractiveController:
    """
    Manages and executes the state-driven interactive session using a state stack
    for robust navigation.
    """

    def __init__(self, session: Session, history_stack: Optional[list[State]] = None):
        """
        Initializes the interactive controller.

        Args:
            session: The global session object.
            history_stack: An optional pre-populated history stack, used for
                           resuming a previous session.
        """
        from .states.menu_states import MainMenuState

        self.session = session
        self.history_stack: list[State] = history_stack or [MainMenuState()]

    @property
    def current_state(self) -> State:
        """The current active state is the top of the stack."""
        return self.history_stack[-1]

    def run(self) -> None:
        """
        Starts and runs the state machine loop until an exit condition is met
        (e.g., an empty history stack or an explicit stop signal).
        """
        logger.info(
            f"Starting controller with initial state: {self.current_state.__class__.__name__}"
        )
        while self.history_stack and self.session.is_running:
            try:
                result = self.current_state.run(self.session)

                if result is None:
                    logger.info("Exit signal received from state. Stopping controller.")
                    self.history_stack.clear()
                    break

                if result is GoBack:
                    if len(self.history_stack) > 1:
                        self.history_stack.pop()
                        logger.debug(
                            f"Navigating back to: {self.current_state.__class__.__name__}"
                        )
                    else:
                        logger.info("Cannot go back from root state. Exiting.")
                        self.history_stack.clear()

                elif isinstance(result, State):
                    self.history_stack.append(result)
                    logger.debug(
                        f"Transitioning forward to: {result.__class__.__name__}"
                    )

            except Exception:
                logger.exception(
                    "An unhandled error occurred in the interactive session."
                )
                self.session.stop()
                self.history_stack.clear()

        logger.info("Interactive session finished.")
