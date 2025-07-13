import shutil
import subprocess

from ....core.config import RofiConfig
from ..base import BaseSelector


class RofiSelector(BaseSelector):
    def __init__(self, config: RofiConfig):
        self.config = config
        self.executable = shutil.which("rofi")
        if not self.executable:
            raise FileNotFoundError("rofi executable not found in PATH.")

    def choose(self, prompt, choices, *, preview=None, header=None):
        rofi_input = "\n".join(choices)

        args = [
            self.executable,
            "-no-config",
            "-theme",
            self.config.theme_main,
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
            return choice

    def confirm(self, prompt, *, default=False):
        # Maps directly to your existing `confirm` method
        # ... (logic from your `Rofi.confirm` method) ...
        pass

    def ask(self, prompt, *, default=None):
        # Maps directly to your existing `ask` method
        # ... (logic from your `Rofi.ask` method) ...
        pass
