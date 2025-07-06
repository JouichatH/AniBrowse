from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ...session import Session


class State(abc.ABC):
    """Abstract Base Class for a state in the workflow."""

    @abc.abstractmethod
    def run(self, session: Session) -> Optional[State | type[GoBack]]:
        """
        Executes the logic for this state.

        This method should contain the primary logic for a given UI screen
        or background task. It orchestrates calls to the UI and actions layers
        and determines the next step in the application flow.

        Args:
            session: The global session object containing all context.

        Returns:
            - A new State instance to transition to for forward navigation.
            - The `GoBack` class to signal a backward navigation.
            - None to signal an application exit.
        """
        pass


# --- Navigation Signals ---
class GoBack:
    """A signal class to indicate a backward navigation request from a state."""

    pass
