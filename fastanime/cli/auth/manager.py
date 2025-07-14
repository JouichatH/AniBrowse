import json
import logging
from typing import Optional

from ...core.constants import USER_DATA_PATH
from ...core.exceptions import ConfigError
from ...libs.api.types import UserProfile

logger = logging.getLogger(__name__)


class AuthManager:
    """
    Handles loading, saving, and clearing of user credentials and profile data.

    This class abstracts the storage mechanism (currently a JSON file), allowing
    for future changes (e.g., to a system keyring) without affecting the rest
    of the application.
    """

    def __init__(self):
        """Initializes the manager with the path to the user data file."""
        self.path = USER_DATA_PATH

    def load_user_profile(self) -> Optional[dict]:
        """
        Loads the user profile data from the JSON file.

        Returns:
            A dictionary containing user data, or None if the file doesn't exist
            or is invalid.
        """
        if not self.path.exists():
            return None
        try:
            with self.path.open("r", encoding="utf-8") as f:
                # We return the raw dict here. The API client will validate it.
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load user credentials from {self.path}: {e}")
            # If the file is corrupt, it's safer to treat it as non-existent.
            return None

    def save_user_profile(self, profile: UserProfile, token: str) -> None:
        """
        Saves the user profile and token to the JSON file.

        Args:
            profile: The generic UserProfile dataclass from the API client.
            token: The authentication token string.
        """
        # This structure matches the old format for backward compatibility
        # and for the AniListApi to re-authenticate from storage.
        user_data = {
            "id": profile.id,
            "name": profile.name,
            "bannerImage": profile.banner_url,
            "avatar": {"large": profile.avatar_url, "medium": profile.avatar_url},
            "token": token,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2)
            logger.info(f"Successfully saved user credentials to {self.path}")
        except IOError as e:
            raise ConfigError(f"Could not save user credentials to {self.path}: {e}")

    def clear_user_profile(self) -> None:
        """Deletes the user credentials file."""
        if self.path.exists():
            try:
                self.path.unlink()
                logger.info("Cleared user credentials.")
            except IOError as e:
                raise ConfigError(
                    f"Could not clear user credentials at {self.path}: {e}"
                )
