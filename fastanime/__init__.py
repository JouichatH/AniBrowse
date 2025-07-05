import sys
import importlib.metadata

if sys.version_info < (3, 10):
    raise ImportError(
        "You are using an unsupported version of Python. Only Python versions 3.10 and above are supported by FastAnime"
    )


__version__ = importlib.metadata.version("FastAnime")

APP_NAME = "FastAnime"
AUTHOR = "Benexl"
GIT_REPO = "github.com"
REPO = f"{GIT_REPO}/{AUTHOR}/{APP_NAME}"


def FastAnime():
    from .cli import run_cli

    run_cli()
