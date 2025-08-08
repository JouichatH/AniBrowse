import click
from fastanime.core.config import AppConfig


@click.command(name="list", help="List items in the download queue and their statuses.")
@click.option("--status", type=click.Choice(["queued", "downloading", "completed", "failed", "paused"]))
@click.pass_obj
def list_cmd(config: AppConfig, status: str | None):
    from fastanime.cli.service.registry import MediaRegistryService
    from fastanime.cli.service.registry.models import DownloadStatus
    from fastanime.cli.service.feedback import FeedbackService

    feedback = FeedbackService(config)
    registry = MediaRegistryService(config.general.media_api, config.media_registry)

    status_map = {
        "queued": DownloadStatus.QUEUED,
        "downloading": DownloadStatus.DOWNLOADING,
        "completed": DownloadStatus.COMPLETED,
        "failed": DownloadStatus.FAILED,
        "paused": DownloadStatus.PAUSED,
    }

    if status:
        target = status_map[status]
        episodes = registry.get_episodes_by_download_status(target)
        feedback.info(f"{len(episodes)} episode(s) with status {status}.")
        for media_id, ep in episodes:
            feedback.info(f"- media:{media_id} episode:{ep}")
    else:
        from rich.table import Table
        from rich.console import Console

        stats = registry.get_download_statistics()
        table = Table(title="Queue Status")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Queued", str(stats.get("queued", 0)))
        table.add_row("Downloading", str(stats.get("downloading", 0)))
        table.add_row("Completed", str(stats.get("downloaded", 0)))
        table.add_row("Failed", str(stats.get("failed", 0)))
        table.add_row("Paused", str(stats.get("paused", 0)))

        console = Console()
        console.print(table)
