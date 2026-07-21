import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import IO, Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def _pid_alive(pid: int) -> bool:
    """Whether a process with this PID exists on THIS machine (lock files are local)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        # os.kill(pid, 0) is NOT a liveness probe on Windows (it terminates the
        # target), so query the process handle instead.
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        ERROR_ACCESS_DENIED = 5
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
        if not handle:
            # Access denied means the process exists but is not ours.
            return ctypes.get_last_error() == ERROR_ACCESS_DENIED
        try:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return exit_code.value == STILL_ACTIVE
            return True
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class NO_DEFAULT:
    pass


def sanitize_filename(s, restricted=False, is_id=NO_DEFAULT):
    """Sanitizes a string so it could be used as part of a filename.
    @param restricted   Use a stricter subset of allowed characters
    @param is_id        Whether this is an ID that should be kept unchanged if possible.
                        If unset, yt-dlp's new sanitization rules are in effect
    """
    import itertools
    import unicodedata
    import re

    ACCENT_CHARS = dict(
        zip(
            "ÂÃÄÀÁÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖŐØŒÙÚÛÜŰÝÞßàáâãäåæçèéêëìíîïðñòóôõöőøœùúûüűýþÿ",
            itertools.chain(
                "AAAAAA",
                ["AE"],
                "CEEEEIIIIDNOOOOOOO",
                ["OE"],
                "UUUUUY",
                ["TH", "ss"],
                "aaaaaa",
                ["ae"],
                "ceeeeiiiionooooooo",
                ["oe"],
                "uuuuuy",
                ["th"],
                "y",
            ),
        )
    )

    if s == "":
        return ""

    def replace_insane(char):
        if restricted and char in ACCENT_CHARS:
            return ACCENT_CHARS[char]
        elif not restricted and char == "\n":
            return "\0 "
        elif is_id is NO_DEFAULT and not restricted and char in '"*:<>?|/\\':
            # Replace with their full-width unicode counterparts
            return {"/": "\u29f8", "\\": "\u29f9"}.get(char, chr(ord(char) + 0xFEE0))
        elif char == "?" or ord(char) < 32 or ord(char) == 127:
            return ""
        elif char == '"':
            return "" if restricted else "'"
        elif char == ":":
            return "\0_\0-" if restricted else "\0 \0-"
        elif char in "\\/|*<>":
            return "\0_"
        if restricted and (
            char in "!&'()[]{}$;`^,#" or char.isspace() or ord(char) > 127
        ):
            return "" if unicodedata.category(char)[0] in "CM" else "\0_"
        return char

    # Replace look-alike Unicode glyphs
    if restricted and (is_id is NO_DEFAULT or not is_id):
        s = unicodedata.normalize("NFKC", s)
    s = re.sub(
        r"[0-9]+(?::[0-9]+)+", lambda m: m.group(0).replace(":", "_"), s
    )  # Handle timestamps
    result = "".join(map(replace_insane, s))
    if is_id is NO_DEFAULT:
        result = re.sub(
            r"(\0.)(?:(?=\1)..)+", r"\1", result
        )  # Remove repeated substitute chars
        STRIP_RE = r"(?:\0.|[ _-])*"
        result = re.sub(
            f"^\0.{STRIP_RE}|{STRIP_RE}\0.$", "", result
        )  # Remove substitute chars from start/end
    result = result.replace("\0", "") or "_"

    if not is_id:
        while "__" in result:
            result = result.replace("__", "_")
        result = result.strip("_")
        # Common case of "Foreign band name - English song title"
        if restricted and result.startswith("-_"):
            result = result[2:]
        if result.startswith("-"):
            result = "_" + result[len("-") :]
        result = result.lstrip(".")
        if not result:
            result = "_"
    return result


def get_file_modification_time(filepath: Path) -> float:
    """
    Returns the modification time of a file as a Unix timestamp.
    Returns 0 if the file does not exist.
    """
    if filepath.exists():
        return filepath.stat().st_mtime
    return 0


def check_file_modified(filepath: Path, previous_mtime: float) -> tuple[float, bool]:
    """
    Checks if a file has been modified since a given previous modification time.
    """
    current_mtime = get_file_modification_time(filepath)
    return current_mtime, current_mtime > previous_mtime


class AtomicWriter:
    """
    A context manager for performing atomic file writes.

    Writes are first directed to a temporary file. If the 'with' block
    completes successfully, the temporary file is atomically renamed
    to the target path, ensuring that the target file is never in
    a partially written or corrupted state. If an error occurs, the
    temporary file is cleaned up, and the original target file remains
    untouched.

    Usage:
        # For text files
        with AtomicWriter(Path("my_file.txt"), mode="w", encoding="utf-8") as f:
            f.write("Hello, world!\n")
            f.write("This is an atomic write.")

        # For binary files
        with AtomicWriter(Path("binary_data.bin"), mode="wb") as f:
            f.write(b"\x01\x02\x03\x04")
    """

    def __init__(
        self, target_path: Path, mode: str = "w", encoding: Union[str, None] = "utf-8"
    ):
        """
        Initializes the AtomicWriter.

        Args:
            target_path: The Path object for the final destination file.
            mode: The file opening mode (e.g., 'w', 'wb'). Only write modes are supported.
                  'a' (append) and 'x' (exclusive creation) modes are not supported
                  as this class is designed for full file replacement.
            encoding: The encoding to use for text modes ('w', 'wt').
                      Should be None for binary modes ('wb').

        Raises:
            ValueError: If an unsupported file mode is provided.
        """
        if "a" in mode:
            raise ValueError(
                "AtomicWriter does not support 'append' mode ('a'). "
                "It's designed for full file replacement."
            )
        if "x" in mode:
            raise ValueError(
                "AtomicWriter does not support 'exclusive creation' mode ('x'). "
                "It handles creation/replacement atomically."
            )
        if "r" in mode:
            raise ValueError("AtomicWriter is for writing, not reading.")
        if "b" in mode and encoding is not None:
            raise ValueError("Encoding must be None for binary write modes ('wb').")
        if "b" not in mode and encoding is None:
            raise ValueError(
                "Encoding must be specified for text write modes ('w', 'wt')."
            )

        self.target_path = target_path
        self.mode = mode
        self.encoding = encoding

        temp_filename = f"{target_path.name}.{os.getpid()}.{uuid.uuid4()}.tmp"
        self.temp_path = target_path.parent / temp_filename

        self._file_handle: Union[IO[Any], None] = None

    def __enter__(self) -> IO[Any]:
        """
        Enters the context, opens the temporary file for writing,
        and returns the file handle.

        Ensures the parent directory of the target file exists.

        Returns:
            A file-like object (TextIO or BinaryIO) for writing.

        Raises:
            Exception: If there's an error opening the temporary file.
        """
        try:
            self.target_path.parent.mkdir(parents=True, exist_ok=True)

            self._file_handle = self.temp_path.open(
                mode=self.mode, encoding=self.encoding
            )
            return self._file_handle
        except Exception as e:
            logger.error(f"Error opening temporary file {self.temp_path}: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        Exits the context. Closes the temporary file.

        If no exception occurred within the 'with' block, atomically renames
        the temporary file to the target path. Otherwise, cleans up the
        temporary file, ensuring the original target file remains untouched.

        Args:
            exc_type: The type of exception raised in the 'with' block (or None).
            exc_val: The exception instance (or None).
            exc_tb: The traceback object (or None).

        Returns:
            False: To propagate any exception that occurred within the 'with' block.
                   (Returning True would suppress the exception).
        """
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

        if exc_type is None:
            try:
                os.replace(self.temp_path, self.target_path)
                logger.debug(f"Successfully wrote atomically to {self.target_path}")
            except OSError as e:
                logger.error(
                    f"Error renaming temporary file {self.temp_path} to {self.target_path}: {e}"
                )
                try:
                    self.temp_path.unlink(missing_ok=True)
                except OSError as cleanup_e:
                    logger.error(
                        f"Failed to clean up temporary file {self.temp_path} after rename error: {cleanup_e}"
                    )
                raise
        else:
            logger.debug(
                f"An error occurred during write. Cleaning up temporary file {self.temp_path}."
            )
            try:
                self.temp_path.unlink(missing_ok=True)
            except OSError as e:
                logger.error(f"Error cleaning up temporary file {self.temp_path}: {e}")
        return False


class FileLock:
    def __init__(
        self, lock_file_path: Path, timeout: float = 300, stale_timeout: float = 300
    ):
        """
        Initializes a file-based lock.

        Args:
            lock_file_path: The Path object for the lock file.
            timeout: How long (in seconds) to wait to acquire the lock.
                     Set to 0 for non-blocking attempt. Set to -1 for indefinite wait.
            stale_timeout: If the lock file is older than this (in seconds),
                           it's considered stale and will be broken.
        """
        self.lock_file_path = lock_file_path
        self.timeout = timeout
        self.stale_timeout = stale_timeout
        self._acquired = False
        self._pid = os.getpid()  # Get current process ID

    def _acquire_atomic(self) -> bool:
        """
        Attempts to atomically create the lock file.
        Returns True on success, False on failure (file already exists).
        Writes the PID and timestamp to the lock file.
        """
        try:
            # Use 'x' mode for atomic creation: create only if it doesn't exist.
            # If it exists, FileExistsError is raised.
            with self.lock_file_path.open("x") as f:
                f.write(f"{self._pid}\n{time.time()}")
            return True
        except FileExistsError:
            return False
        except Exception as e:
            # Handle other potential errors during file creation/write
            logger.error(f"Error creating lock file {self.lock_file_path}: {e}")
            return False

    def _read_lock_info(self) -> Optional[Tuple[int, float]]:
        """Read (pid, timestamp) from the lock file; None if unreadable/corrupt/gone."""
        try:
            with self.lock_file_path.open("r") as f:
                lines = f.readlines()
            return int(lines[0].strip()), float(lines[1].strip())
        except (ValueError, IndexError, FileNotFoundError, OSError):
            return None

    def _is_stale(self) -> bool:
        """
        A lock is stale when its owning process is dead, when it is too old,
        or when its content is unreadable/corrupt.
        """
        if not self.lock_file_path.exists():
            return False  # Not stale if it doesn't exist

        info = self._read_lock_info()
        if info is None:
            logger.warning(
                f"Could not read or parse lock file {self.lock_file_path}. Assuming it's stale due to potential corruption."
            )
            return True

        pid, locked_timestamp = info
        # A lock whose owner is gone can never be released; break it right away
        # instead of stalling every registry write for stale_timeout seconds.
        # (This is exactly what happens when the app window is closed mid-write.)
        if not _pid_alive(pid):
            logger.warning(
                f"Lock file {self.lock_file_path} is held by dead PID {pid}. Considering it stale."
            )
            return True
        if time.time() - locked_timestamp > self.stale_timeout:
            logger.warning(
                f"Lock file {self.lock_file_path} is older than {self.stale_timeout} seconds. Considering it stale."
            )
            return True
        return False

    def _unlink_with_retry(self, attempts: int = 20, delay: float = 0.05) -> bool:
        """
        Delete the lock file, retrying briefly. On Windows the unlink fails with
        WinError 32 while ANOTHER process momentarily has the file open in its
        own _is_stale() read poll; those reads last well under `delay`, so a few
        retries ride out the collision instead of leaving the lock behind.
        """
        for _ in range(attempts):
            try:
                self.lock_file_path.unlink(missing_ok=True)
                return True
            except OSError:
                time.sleep(delay)
        return False

    def acquire(self):
        """
        Attempts to acquire the lock. Blocks until acquired or timeout occurs.
        """
        start_time = time.time()
        while True:
            if self._acquire_atomic():
                self._acquired = True
                logger.debug(f"Lock acquired by PID {self._pid}.")
                return

            if self._is_stale():
                logger.debug(
                    f"Existing lock file {self.lock_file_path} is stale. Attempting to break it."
                )
                # Re-read before deleting: if the content changed since the
                # staleness check, another waiter already broke this lock and
                # acquired a FRESH one - deleting now would steal its lock and
                # let two processes write concurrently.
                stale_info = self._read_lock_info()
                still_stale = (
                    stale_info is None
                    or not _pid_alive(stale_info[0])
                    or time.time() - stale_info[1] > self.stale_timeout
                )
                if still_stale:
                    if self._unlink_with_retry() and self._acquire_atomic():
                        self._acquired = True
                        logger.debug(
                            f"Stale lock broken and new lock acquired by PID {self._pid}."
                        )
                        return

            if self.timeout >= 0 and time.time() - start_time > self.timeout:
                raise TimeoutError(
                    f"Failed to acquire lock {self.lock_file_path} within {self.timeout} seconds."
                )

            sleep_time = 0.1
            if self.timeout == -1:
                logger.debug(f"Waiting for lock {self.lock_file_path} indefinitely...")
                time.sleep(sleep_time)
            elif self.timeout > 0:
                logger.debug(
                    f"Waiting for lock {self.lock_file_path} ({round(self.timeout - (time.time() - start_time), 1)}s remaining)..."
                )
                time.sleep(
                    min(
                        sleep_time,
                        self.timeout - (time.time() - start_time)
                        if self.timeout - (time.time() - start_time) > 0
                        else sleep_time,
                    )
                )
            else:
                raise BlockingIOError(
                    f"Lock {self.lock_file_path} is currently held by another process (non-blocking)."
                )

    def release(self):
        """
        Releases the lock by deleting the lock file.
        """
        if self._acquired:
            # Releasing must not leave the file behind: a leftover lock with our
            # fresh timestamp stalls every other writer for stale_timeout.
            if self._unlink_with_retry():
                logger.debug(f"Lock released by PID {self._pid}.")
            else:
                logger.error(
                    f"Error releasing lock file {self.lock_file_path}: still in use after retries"
                )
            self._acquired = False
        else:
            logger.warning(
                "Attempted to release a lock that was not acquired by PID {self._pid}."
            )

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
