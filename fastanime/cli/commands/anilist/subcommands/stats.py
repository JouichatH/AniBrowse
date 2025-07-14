from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from fastanime.core.config import AppConfig


@click.command(help="Print out your anilist stats")
@click.pass_obj
def stats(config: "AppConfig"):
    import shutil
    import subprocess

    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    from fastanime.core.exceptions import FastAnimeError
    from fastanime.libs.api.factory import create_api_client
    from fastanime.cli.utils.feedback import create_feedback_manager

    feedback = create_feedback_manager(config.general.icons)
    console = Console()

    try:
        # Create API client and ensure authentication
        api_client = create_api_client(config.general.api_client, config)
        
        if not api_client.user_profile:
            feedback.error(
                "Not authenticated", 
                "Please run: fastanime anilist login"
            )
            raise click.Abort()

        user_profile = api_client.user_profile

        # Check if kitten is available for image display
        KITTEN_EXECUTABLE = shutil.which("kitten")
        if not KITTEN_EXECUTABLE:
            feedback.warning("Kitten not found - profile image will not be displayed")
        else:
            # Display profile image using kitten icat
            if user_profile.avatar_url:
                console.clear()
                image_x = int(console.size.width * 0.1)
                image_y = int(console.size.height * 0.1)
                img_w = console.size.width // 3
                img_h = console.size.height // 3
                
                image_process = subprocess.run(
                    [
                        KITTEN_EXECUTABLE,
                        "icat",
                        "--clear",
                        "--place",
                        f"{img_w}x{img_h}@{image_x}x{image_y}",
                        user_profile.avatar_url,
                    ],
                    check=False,
                )
                
                if image_process.returncode != 0:
                    feedback.warning("Failed to display profile image")

        # Display user information
        about_text = getattr(user_profile, 'about', '') or "No description available"
        
        console.print(
            Panel(
                Markdown(about_text),
                title=f"📊 {user_profile.name}'s Profile",
            )
        )

        # You can add more stats here if the API provides them
        feedback.success("User profile displayed successfully")

    except FastAnimeError as e:
        feedback.error("Failed to fetch user stats", str(e))
        raise click.Abort()
    except Exception as e:
        feedback.error("Unexpected error occurred", str(e))
        raise click.Abort()
