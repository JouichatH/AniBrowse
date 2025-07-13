import sys


def custom_exception_hook(exc_type, exc_value, exc_traceback):
    print(f"{exc_type.__name__}: {exc_value}")


default_exception_hook = sys.excepthook
# sys.tracebacklimit = 0


def setup_exceptions_handler(trace: bool | None, dev: bool | None):
    if trace or dev:
        sys.excepthook = default_exception_hook
    else:
        sys.excepthook = custom_exception_hook
