import click

from ...core.config import AppConfig


@click.command(
    help="Manage your config with ease",
    short_help="Edit your config",
    epilog="""
\b
\b\bExamples:
  # Edit your config in your default editor 
  # NB: If it opens vim or vi exit with `:q`
  fastanime config
\b
  # get the path of the config file
  fastanime config --path
\b
  # print desktop entry info
  fastanime config --desktop-entry
\b
  # update your config without opening an editor
  fastanime --icons --fzf --preview config --update
\b 
  # view the current contents of your config
  fastanime config --view
""",
)
@click.option("--path", "-p", help="Print the config location and exit", is_flag=True)
@click.option(
    "--view", "-v", help="View the current contents of your config", is_flag=True
)
@click.option(
    "--desktop-entry",
    "-d",
    help="Configure the desktop entry of fastanime",
    is_flag=True,
)
@click.option(
    "--update",
    "-u",
    help="Persist all the config options passed to fastanime to your config file",
    is_flag=True,
)
@click.pass_obj
def config(user_config: AppConfig, path, view, desktop_entry, update):
    from ..config.generate import generate_config_ini_from_app_model
    from ..constants import USER_CONFIG_PATH

    if path:
        print(USER_CONFIG_PATH)
    elif view:
        print(generate_config_ini_from_app_model(user_config))
    elif desktop_entry:
        _generate_desktop_entry()
    elif update:
        with open(USER_CONFIG_PATH, "w", encoding="utf-8") as file:
            file.write(generate_config_ini_from_app_model(user_config))
        print("update successfull")
    else:
        click.edit(filename=str(USER_CONFIG_PATH))


def _generate_desktop_entry():
    """
    Generates a desktop entry for FastAnime.
    """
    import os
    import shutil
    import sys
    from pathlib import Path
    from textwrap import dedent

    from rich import print
    from rich.prompt import Confirm

    from ... import __version__
    from ..constants import APP_NAME, ICON_PATH, PLATFORM

    FASTANIME_EXECUTABLE = shutil.which("fastanime")
    if FASTANIME_EXECUTABLE:
        cmds = f"{FASTANIME_EXECUTABLE} --rofi anilist"
    else:
        cmds = f"{sys.executable} -m fastanime --rofi anilist"

    # TODO: Get funs of the other platforms to complete this lol
    if PLATFORM == "win32":
        print(
            "Not implemented; the author thinks its not straight forward so welcomes lovers of windows to try and implement it themselves or to switch to a proper os like arch linux or pray the author gets bored 😜"
        )
    elif PLATFORM == "darwin":
        print(
            "Not implemented; the author thinks its not straight forward so welcomes lovers of mac to try and implement it themselves  or to switch to a proper os like arch linux or pray the author gets bored 😜"
        )
    else:
        desktop_entry = dedent(
            f"""
            [Desktop Entry]
            Name={APP_NAME}
            Type=Application
            version={__version__}
            Path={Path().home()}
            Comment=Watch anime from your terminal 
            Terminal=false
            Icon={ICON_PATH}
            Exec={cmds}
            Categories=Entertainment
        """
        )
        base = os.path.expanduser("~/.local/share/applications")
        desktop_entry_path = os.path.join(base, f"{APP_NAME}.desktop")
        if os.path.exists(desktop_entry_path):
            if not Confirm.ask(
                f"The file already exists {desktop_entry_path}; or would you like to rewrite it",
                default=False,
            ):
                return
        with open(desktop_entry_path, "w") as f:
            f.write(desktop_entry)
        with open(desktop_entry_path) as f:
            print(f"Successfully wrote \n{f.read()}")
