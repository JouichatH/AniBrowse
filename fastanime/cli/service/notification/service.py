import json
import logging
from typing import Set

from fastanime.core.constants import APP_CACHE_DIR
from fastanime.libs.media_api.base import BaseApiClient

try:
    import plyer

    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

logger = logging.getLogger(__name__)
SEEN_NOTIFICATIONS_CACHE = APP_CACHE_DIR / "seen_notifications.json"


class NotificationService:
    def __init__(self, media_api: BaseApiClient):
        self.media_api = media_api
        self._seen_ids: Set[int] = self._load_seen_ids()

    def _load_seen_ids(self) -> Set[int]:
        if not SEEN_NOTIFICATIONS_CACHE.exists():
            return set()
        try:
            with open(SEEN_NOTIFICATIONS_CACHE, "r") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, IOError):
            return set()

    def _save_seen_ids(self):
        try:
            with open(SEEN_NOTIFICATIONS_CACHE, "w") as f:
                json.dump(list(self._seen_ids), f)
        except IOError:
            logger.error("Failed to save seen notifications cache.")

    def check_and_display_notifications(self):
        if not PLYER_AVAILABLE:
            logger.warning("plyer not installed. Cannot display desktop notifications.")
            return

        if not self.media_api.is_authenticated():
            logger.info("Not authenticated, skipping notification check.")
            return

        logger.info("Checking for new notifications...")
        notifications = self.media_api.get_notifications()

        if not notifications:
            logger.info("No new notifications found.")
            return

        new_notifications = [n for n in notifications if n.id not in self._seen_ids]

        if not new_notifications:
            logger.info("No unseen notifications found.")
            return

        for notif in new_notifications:
            title = notif.media.title.english or notif.media.title.romaji
            message = f"Episode {notif.episode} of {title} has aired!"

            try:
                plyer.notification.notify(
                    title="FastAnime: New Episode",
                    message=message,
                    app_name="FastAnime",
                    timeout=20,
                )
                logger.info(f"Displayed notification: {message}")
                self._seen_ids.add(notif.id)
            except Exception as e:
                logger.error(f"Failed to display notification: {e}")

        self._save_seen_ids()
