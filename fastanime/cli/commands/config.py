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
  # Start the interactive configuration wizard
  fastanime config --interactive
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
    "--view-json",
    "-vj",
    help="View the current contents of your config in json format",
    is_flag=True,
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
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Start the interactive configuration wizard.",
)
@click.pass_obj
def config(
    user_config: AppConfig, path, view, view_json, desktop_entry, update, interactive
):
    from ...core.constants import USER_CONFIG
    from ..config.editor import InteractiveConfigEditor
    from ..config.generate import generate_config_ini_from_app_model

    if path:
        print(USER_CONFIG)
    elif view:
        from rich.console import Console
        from rich.syntax import Syntax

        console = Console()
        config_ini = generate_config_ini_from_app_model(user_config)
        syntax = Syntax(
            config_ini,
            "ini",
            theme=user_config.general.pygment_style,
            line_numbers=True,
            word_wrap=True,
        )
        console.print(syntax)
    elif view_json:
        import json

        print(json.dumps(user_config.model_dump(mode="json")))
    elif desktop_entry:
        _generate_desktop_entry()
    elif interactive:
        editor = InteractiveConfigEditor(current_config=user_config)
        new_config = editor.run()
        with open(USER_CONFIG, "w", encoding="utf-8") as file:
            file.write(generate_config_ini_from_app_model(new_config))
        click.echo(f"Configuration saved successfully to {USER_CONFIG}")
    elif update:
        with open(USER_CONFIG, "w", encoding="utf-8") as file:
            file.write(generate_config_ini_from_app_model(user_config))
        print("update successfull")
    else:
        click.edit(filename=str(USER_CONFIG))


def _generate_desktop_entry():
    """
    Generates a desktop entry for FastAnime.
    """
    import shutil
    import sys
    from pathlib import Path
    from textwrap import dedent

    from rich import print
    from rich.prompt import Confirm

    from ...core.constants import (
        ICON_PATH,
        PLATFORM,
        PROJECT_NAME,
        USER_APPLICATIONS,
        __version__,
    )

    EXECUTABLE = shutil.which("fastanime")
    if EXECUTABLE:
        cmds = f"{EXECUTABLE} --rofi anilist"
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
            Name={PROJECT_NAME}
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
        desktop_entry_path = USER_APPLICATIONS / f"{PROJECT_NAME}.desktop"
        if desktop_entry_path.exists():
            if not Confirm.ask(
                f"The file already exists {desktop_entry_path}; or would you like to rewrite it",
                default=False,
            ):
                return
        with open(desktop_entry_path, "w") as f:
            f.write(desktop_entry)
        with open(desktop_entry_path) as f:
            print(f"Successfully wrote \n{f.read()}")
