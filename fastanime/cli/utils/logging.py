import logging

from rich.traceback import install as rich_install

from ...core.constants import LOG_FILE_PATH


def setup_logging(
    log: bool | None, log_file: bool | None, rich_traceback: bool | None
) -> None:
    """Configures the application's logging based on CLI flags."""
    if rich_traceback:
        rich_install(show_locals=True)

    if log:
        from rich.logging import RichHandler

        logging.basicConfig(
            level="DEBUG",
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler()],
        )
        logging.getLogger(__name__).info("Rich logging initialized.")
    elif log_file:
        logging.basicConfig(
            level="DEBUG",
            filename=LOG_FILE_PATH,
            format="%(asctime)s %(levelname)s: %(message)s",
            datefmt="[%d/%m/%Y@%H:%M:%S]",
            filemode="w",
        )
    else:
        logging.basicConfig(level="CRITICAL")
