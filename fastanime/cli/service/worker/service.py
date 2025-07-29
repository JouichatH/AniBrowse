import logging
import time

from fastanime.cli.service.download.service import DownloadService
from fastanime.cli.service.notification.service import NotificationService
from fastanime.core.config.model import WorkerConfig

logger = logging.getLogger(__name__)


class BackgroundWorkerService:
    def __init__(
        self,
        config: WorkerConfig,
        notification_service: NotificationService,
        download_service: DownloadService,
    ):
        self.config = config
        self.notification_service = notification_service
        self.download_service = download_service
        self.running = True

    def run(self):
        logger.info("Background worker started.")
        last_notification_check = 0
        last_download_check = 0

        notification_interval_sec = self.config.notification_check_interval * 60
        download_interval_sec = self.config.download_check_interval * 60
        self.download_service.start()

        try:
            while self.running:
                current_time = time.time()

                # Check for notifications
                if current_time - last_notification_check > notification_interval_sec:
                    try:
                        self.notification_service.check_and_display_notifications()
                    except Exception as e:
                        logger.error(f"Error during notification check: {e}")
                    last_notification_check = current_time

                # Process download queue
                if current_time - last_download_check > download_interval_sec:
                    try:
                        self.download_service.resume_unfinished_downloads()
                    except Exception as e:
                        logger.error(f"Error during download queue processing: {e}")
                    last_download_check = current_time

                # Sleep for a short interval to prevent high CPU usage
                time.sleep(30)  # Sleep for 30 seconds before next check cycle

        except KeyboardInterrupt:
            logger.info("Background worker stopped by user.")
            self.stop()

    def stop(self):
        self.running = False
        logger.info("Background worker shutting down.")
