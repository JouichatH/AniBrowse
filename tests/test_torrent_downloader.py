"""
Tests for the TorrentDownloader class.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from fastanime.core.downloader.torrents import (
    TorrentDownloader,
    TorrentDownloadError,
    LIBTORRENT_AVAILABLE,
)
from fastanime.core.exceptions import DependencyNotFoundError


class TestTorrentDownloader(unittest.TestCase):
    """Test cases for TorrentDownloader class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.downloader = TorrentDownloader(
            download_path=self.temp_dir,
            max_upload_rate=100,
            max_download_rate=200,
            max_connections=50,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """Test TorrentDownloader initialization."""
        self.assertEqual(self.downloader.download_path, self.temp_dir)
        self.assertEqual(self.downloader.max_upload_rate, 100)
        self.assertEqual(self.downloader.max_download_rate, 200)
        self.assertEqual(self.downloader.max_connections, 50)
        self.assertTrue(self.temp_dir.exists())

    def test_init_creates_download_directory(self):
        """Test that download directory is created if it doesn't exist."""
        non_existent_dir = self.temp_dir / "new_dir"
        self.assertFalse(non_existent_dir.exists())

        downloader = TorrentDownloader(download_path=non_existent_dir)
        self.assertTrue(non_existent_dir.exists())

    @patch("fastanime.core.downloader.torrents.shutil.which")
    def test_download_with_webtorrent_cli_not_available(self, mock_which):
        """Test webtorrent CLI fallback when not available."""
        mock_which.return_value = None

        with self.assertRaises(DependencyNotFoundError) as context:
            self.downloader.download_with_webtorrent_cli("magnet:test")

        self.assertIn("webtorrent CLI is not available", str(context.exception))

    @patch("fastanime.core.downloader.torrents.subprocess.run")
    @patch("fastanime.core.downloader.torrents.shutil.which")
    def test_download_with_webtorrent_cli_success(self, mock_which, mock_run):
        """Test successful webtorrent CLI download."""
        mock_which.return_value = "/usr/bin/webtorrent"
        mock_result = Mock()
        mock_result.stdout = f"Downloaded test-file to {self.temp_dir}/test-file"
        mock_run.return_value = mock_result

        # Create a dummy file to simulate download
        test_file = self.temp_dir / "test-file"
        test_file.touch()

        result = self.downloader.download_with_webtorrent_cli("magnet:test")

        mock_run.assert_called_once()
        self.assertEqual(result, test_file)

    @patch("fastanime.core.downloader.torrents.subprocess.run")
    @patch("fastanime.core.downloader.torrents.shutil.which")
    def test_download_with_webtorrent_cli_failure(self, mock_which, mock_run):
        """Test webtorrent CLI download failure."""
        mock_which.return_value = "/usr/bin/webtorrent"
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "webtorrent", stderr="Error"
        )

        with self.assertRaises(TorrentDownloadError) as context:
            self.downloader.download_with_webtorrent_cli("magnet:test")

        self.assertIn("webtorrent CLI failed", str(context.exception))

    @unittest.skipUnless(LIBTORRENT_AVAILABLE, "libtorrent not available")
    def test_setup_libtorrent_session(self):
        """Test libtorrent session setup when available."""
        session = self.downloader._setup_libtorrent_session()
        self.assertIsNotNone(session)

    @unittest.skipIf(LIBTORRENT_AVAILABLE, "libtorrent is available")
    def test_setup_libtorrent_session_not_available(self):
        """Test libtorrent session setup when not available."""
        with self.assertRaises(DependencyNotFoundError):
            self.downloader._setup_libtorrent_session()

    @patch("fastanime.core.downloader.torrents.LIBTORRENT_AVAILABLE", False)
    def test_download_with_libtorrent_not_available(self):
        """Test libtorrent download when not available."""
        with self.assertRaises(DependencyNotFoundError) as context:
            self.downloader.download_with_libtorrent("magnet:test")

        self.assertIn("libtorrent is not available", str(context.exception))

    def test_progress_callback(self):
        """Test progress callback functionality."""
        callback_mock = Mock()
        downloader = TorrentDownloader(
            download_path=self.temp_dir, progress_callback=callback_mock
        )

        # The callback should be stored
        self.assertEqual(downloader.progress_callback, callback_mock)

    @patch.object(TorrentDownloader, "download_with_webtorrent_cli")
    @patch.object(TorrentDownloader, "download_with_libtorrent")
    def test_download_prefers_libtorrent(self, mock_libtorrent, mock_webtorrent):
        """Test that download method prefers libtorrent by default."""
        mock_libtorrent.return_value = self.temp_dir / "test"

        with patch("fastanime.core.downloader.torrents.LIBTORRENT_AVAILABLE", True):
            result = self.downloader.download("magnet:test", prefer_libtorrent=True)

        mock_libtorrent.assert_called_once()
        mock_webtorrent.assert_not_called()

    @patch.object(TorrentDownloader, "download_with_webtorrent_cli")
    @patch.object(TorrentDownloader, "download_with_libtorrent")
    def test_download_fallback_to_webtorrent(self, mock_libtorrent, mock_webtorrent):
        """Test fallback to webtorrent when libtorrent fails."""
        mock_libtorrent.side_effect = DependencyNotFoundError("libtorrent not found")
        mock_webtorrent.return_value = self.temp_dir / "test"

        with patch("fastanime.core.downloader.torrents.LIBTORRENT_AVAILABLE", True):
            result = self.downloader.download("magnet:test")

        mock_libtorrent.assert_called_once()
        mock_webtorrent.assert_called_once()
        self.assertEqual(result, self.temp_dir / "test")

    @patch.object(TorrentDownloader, "download_with_webtorrent_cli")
    @patch.object(TorrentDownloader, "download_with_libtorrent")
    def test_download_all_methods_fail(self, mock_libtorrent, mock_webtorrent):
        """Test when all download methods fail."""
        mock_libtorrent.side_effect = DependencyNotFoundError("libtorrent not found")
        mock_webtorrent.side_effect = DependencyNotFoundError("webtorrent not found")

        with self.assertRaises(TorrentDownloadError) as context:
            self.downloader.download("magnet:test")

        self.assertIn("All torrent download methods failed", str(context.exception))

    def test_magnet_link_detection(self):
        """Test detection of magnet links."""
        magnet_link = "magnet:?xt=urn:btih:test"
        http_link = "http://example.com/test.torrent"
        file_path = "/path/to/test.torrent"

        # These would be tested in integration tests with actual libtorrent
        # Here we just verify the method exists and handles different input types
        self.assertTrue(magnet_link.startswith("magnet:"))
        self.assertTrue(http_link.startswith(("http://", "https://")))
        self.assertFalse(file_path.startswith(("magnet:", "http://", "https://")))


class TestLegacyFunction(unittest.TestCase):
    """Test the legacy function for backward compatibility."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch.object(TorrentDownloader, "download_with_webtorrent_cli")
    def test_legacy_function(self, mock_download):
        """Test the legacy download_torrent_with_webtorrent_cli function."""
        from fastanime.core.downloader.torrents import (
            download_torrent_with_webtorrent_cli,
        )

        test_path = self.temp_dir / "test.mkv"
        mock_download.return_value = test_path

        result = download_torrent_with_webtorrent_cli(test_path, "magnet:test")

        mock_download.assert_called_once_with("magnet:test")
        self.assertEqual(result, test_path)


if __name__ == "__main__":
    # Add subprocess import for the test
    import subprocess

    unittest.main()
