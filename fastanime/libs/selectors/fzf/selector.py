import logging
import shutil
import subprocess

from ....core.config import FzfConfig
from ..base import BaseSelector

logger = logging.getLogger(__name__)


class FzfSelector(BaseSelector):
    def __init__(self, config: FzfConfig):
        self.config = config
        self.executable = shutil.which("fzf")
        if not self.executable:
            raise FileNotFoundError("fzf executable not found in PATH.")

        # You can prepare default opts here from the config
        if config.opts:
            self.default_opts = self.config.opts.splitlines()
        else:
            self.default_opts = []

    def choose(self, prompt, choices, *, preview=None, header=None):
        fzf_input = "\n".join(choices)

        # Build command from base options and specific arguments
        commands = []
        commands.extend(["--prompt", f"{prompt.title()}: "])
        if header:
            commands.extend(["--header", header])
        if preview:
            commands.extend(["--preview", preview])

        result = subprocess.run(
            [self.executable, *commands],
            input=fzf_input,
            stdout=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def confirm(self, prompt, *, default=False):
        # FZF is not great for confirmation, but we can make it work
        choices = ["Yes", "No"]
        default_choice = "Yes" if default else "No"
        # A simple fzf call can simulate this
        result = self.choose(choices, prompt, header=f"Default: {default_choice}")
        return result == "Yes"

    def ask(self, prompt, *, default=None):
        # Use FZF's --print-query to capture user input
        commands = []
        commands.extend(["--prompt", f"{prompt}: ", "--print-query"])

        result = subprocess.run(
            [self.executable, *commands],
            input="",
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
        # The output contains the selection (if any) and the query on the last line
        lines = result.stdout.strip().splitlines()
        return lines[-1] if lines else (default or "")
