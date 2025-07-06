from __future__ import annotations

import click
from rich import print
from rich.prompt import Confirm, Prompt

from .....cli.auth.manager import CredentialsManager


@click.command(help="Login to your AniList account to enable progress tracking.")
@click.option("--status", "-s", is_flag=True, help="Check current login status.")
@click.option("--logout", "-l", is_flag=True, help="Log out and erase credentials.")
@click.pass_context
def login(ctx: click.Context, status: bool, logout: bool):
    """Handles user authentication and credential management."""
    manager = CredentialsManager()

    if status:
        user_data = manager.load_user_profile()
        if user_data:
            print(f"[bold green]Logged in as:[/] {user_data.get('name')}")
            print(f"User ID: {user_data.get('id')}")
        else:
            print("[bold yellow]Not logged in.[/]")
        return

    if logout:
        if Confirm.ask(
            "[bold red]Are you sure you want to log out and erase your token?[/]"
        ):
            manager.clear_user_profile()
            print("You have been logged out.")
        return

    # --- Start Login Flow ---
    from ....libs.api.factory import create_api_client

    api_client = create_api_client("anilist", ctx.obj)

    click.launch(
        "https://anilist.co/api/v2/oauth/authorize?client_id=20148&response_type=token"
    )
    print("Your browser has been opened to obtain an AniList token.")
    print("After authorizing, copy the token from the address bar and paste it below.")

    token = Prompt.ask("Enter your AniList Access Token")
    if not token.strip():
        print("[bold red]Login cancelled.[/]")
        return

    profile = api_client.authenticate(token.strip())

    if profile:
        manager.save_user_profile(profile, token)
        print(f"[bold green]Successfully logged in as {profile.name}! ✨[/]")
    else:
        print("[bold red]Login failed. The token may be invalid or expired.[/]")
