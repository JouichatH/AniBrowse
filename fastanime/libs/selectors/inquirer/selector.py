from InquirerPy.prompts import FuzzyPrompt
from rich.prompt import Confirm, Prompt

from ..base import BaseSelector


class InquirerSelector(BaseSelector):
    def choose(self, prompt, choices, *, preview=None, header=None):
        if header:
            print(f"[bold cyan]{header}[/bold cyan]")
        return FuzzyPrompt(
            message=prompt,
            choices=choices,
            height="100%",
            border=True,
            validate=lambda result: result in choices,
        ).execute()

    def confirm(self, prompt, *, default=False):
        return Confirm.ask(prompt, default=default)

    def ask(self, prompt, *, default=None):
        return Prompt.ask(prompt=prompt, default=default or "")
