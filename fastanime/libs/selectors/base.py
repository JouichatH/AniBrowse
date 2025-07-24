from abc import ABC, abstractmethod
from typing import List, Optional


class BaseSelector(ABC):
    """
    Abstract Base Class for user-facing selectors (FZF, Rofi, etc.).
    Defines the common interface for all selection operations.
    """

    @abstractmethod
    def choose(
        self,
        prompt: str,
        choices: List[str],
        *,
        preview: Optional[str] = None,
        header: Optional[str] = None,
    ) -> str | None:
        """
        Prompts the user to choose one item from a list.

        Args:
            prompt: The message to display to the user.
            choices: A list of strings for the user to choose from.
            preview: An optional command or string for a preview window.
            header: An optional header to display above the choices.

        Returns:
            The string of the chosen item.
        """
        pass

    @abstractmethod
    def confirm(self, prompt: str, *, default: bool = False) -> bool:
        """
        Asks the user a yes/no question.

        Args:
            prompt: The question to ask the user.
            default: The default return value if the user just presses Enter.

        Returns:
            True for 'yes', False for 'no'.
        """
        pass

    @abstractmethod
    def ask(self, prompt: str, *, default: Optional[str] = None) -> str | None:
        """
        Asks the user for free-form text input.

        Args:
            prompt: The question to ask the user.
            default: An optional default value.

        Returns:
            The string entered by the user.
        """
        pass
