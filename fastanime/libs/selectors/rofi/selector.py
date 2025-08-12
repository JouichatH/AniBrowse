import shutil
import subprocess

from ....core.config import RofiConfig
from ....core.utils import detect
from ..base import BaseSelector


class RofiSelector(BaseSelector):
    def __init__(self, config: RofiConfig):
        self.config = config
        self.executable = shutil.which("rofi")
        if not self.executable:
            raise FileNotFoundError("rofi executable not found in PATH.")

    def choose(self, prompt, choices, *, preview=None, header=None):
        if preview and detect.is_bash_script(preview):
            preview = None
        rofi_input = preview if preview else "\n".join(choices)

        args = [
            self.executable,
            "-no-config",
            "-theme",
            self.config.theme_preview if preview else self.config.theme_main,
            "-p",
            prompt,
            "-i",
            "-dmenu",
        ]
        if preview:
            args.append("-show-icons")
        result = subprocess.run(
            args,
            input=rofi_input,
            stdout=subprocess.PIPE,
            text=True,
        )

        if result:
            choice = result.stdout.strip()
            return choice

    def confirm(self, prompt, *, default=False):
        choices = ["Yes", "No"]
        default_choice = "Yes" if default else "No"
        result = self.choose(prompt, choices, header=f"Default: {default_choice}")
        return result == "Yes"

    def ask(self, prompt, *, default=None):
        return self.choose(prompt, [])

    def choose_multiple(
        self, prompt: str, choices: list[str], preview: str | None = None
    ) -> list[str]:
        rofi_input = "\n".join(choices)
        args = [
            self.executable,
            "-no-config",
            "-theme",
            self.config.theme_main,
            "-multi-select",
            "-p",
            prompt,
            "-i",
            "-dmenu",
        ]
        result = subprocess.run(
            args,
            input=rofi_input,
            stdout=subprocess.PIPE,
            text=True,
        )

        if result:
            choice = result.stdout.strip()
            return choice.split()
        return []


if __name__ == "__main__":
    config = RofiConfig()
    selector = RofiSelector(config)
    choice = selector.ask("Hello dev :)")
    print(choice)
    choice = selector.confirm("Hello dev :)")
    print(choice)
    choice = selector.choose_multiple("What comes first", ["a", "b"])
    print(choice)
    choice = selector.choose("What comes first", ["a", "b"])
    print(choice)
