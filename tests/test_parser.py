"""Tests for episode range parser."""

import pytest

from fastanime.cli.utils.parser import parse_episode_range


class TestParseEpisodeRange:
    """Test cases for the parse_episode_range function."""
    
    @pytest.fixture
    def episodes(self):
        """Sample episode list for testing."""
        return ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
    
    def test_no_range_returns_all_episodes(self, episodes):
        """Test that None or empty range returns all episodes."""
        result = list(parse_episode_range(None, episodes))
        assert result == episodes
    
    def test_colon_only_returns_all_episodes(self, episodes):
        """Test that ':' returns all episodes."""
        result = list(parse_episode_range(":", episodes))
        assert result == episodes
    
    def test_start_end_range(self, episodes):
        """Test start:end range format."""
        result = list(parse_episode_range("2:5", episodes))
        assert result == ["3", "4", "5"]
    
    def test_start_only_range(self, episodes):
        """Test start: range format."""
        result = list(parse_episode_range("5:", episodes))
        assert result == ["6", "7", "8", "9", "10"]
    
    def test_end_only_range(self, episodes):
        """Test :end range format."""
        result = list(parse_episode_range(":3", episodes))
        assert result == ["1", "2", "3"]
    
    def test_start_end_step_range(self, episodes):
        """Test start:end:step range format."""
        result = list(parse_episode_range("2:8:2", episodes))
        assert result == ["3", "5", "7"]
    
    def test_single_number_range(self, episodes):
        """Test single number format (start from index)."""
        result = list(parse_episode_range("5", episodes))
        assert result == ["6", "7", "8", "9", "10"]
    
    def test_empty_start_end_in_three_part_range_raises_error(self, episodes):
        """Test that empty parts in start:end:step format raise error."""
        with pytest.raises(ValueError, match="When using 3 parts"):
            list(parse_episode_range(":5:2", episodes))
            
        with pytest.raises(ValueError, match="When using 3 parts"):
            list(parse_episode_range("2::2", episodes))
            
        with pytest.raises(ValueError, match="When using 3 parts"):
            list(parse_episode_range("2:5:", episodes))
    
    def test_invalid_integer_raises_error(self, episodes):
        """Test that invalid integers raise ValueError."""
        with pytest.raises(ValueError, match="Must be a valid integer"):
            list(parse_episode_range("abc", episodes))
            
        with pytest.raises(ValueError, match="Start and end must be valid integers"):
            list(parse_episode_range("2:abc", episodes))
            
        with pytest.raises(ValueError, match="All parts must be valid integers"):
            list(parse_episode_range("2:5:abc", episodes))
    
    def test_zero_step_raises_error(self, episodes):
        """Test that zero step raises ValueError."""
        with pytest.raises(ValueError, match="Step value must be positive"):
            list(parse_episode_range("2:5:0", episodes))
    
    def test_negative_step_raises_error(self, episodes):
        """Test that negative step raises ValueError."""
        with pytest.raises(ValueError, match="Step value must be positive"):
            list(parse_episode_range("2:5:-1", episodes))
    
    def test_too_many_colons_raises_error(self, episodes):
        """Test that too many colons raise ValueError."""
        with pytest.raises(ValueError, match="Too many colon separators"):
            list(parse_episode_range("2:5:7:9", episodes))
    
    def test_edge_case_empty_list(self):
        """Test behavior with empty episode list."""
        result = list(parse_episode_range(":", []))
        assert result == []
    
    def test_edge_case_single_episode(self):
        """Test behavior with single episode."""
        episodes = ["1"]
        result = list(parse_episode_range(":", episodes))
        assert result == ["1"]
        
        result = list(parse_episode_range("0:1", episodes))
        assert result == ["1"]
    
    def test_numerical_sorting(self):
        """Test that episodes are sorted numerically, not lexicographically."""
        episodes = ["10", "2", "1", "11", "3"]
        result = list(parse_episode_range(":", episodes))
        assert result == ["1", "2", "3", "10", "11"]
    
    def test_index_out_of_bounds_behavior(self, episodes):
        """Test behavior when indices exceed available episodes."""
        # Python slicing handles out-of-bounds gracefully
        result = list(parse_episode_range("15:", episodes))
        assert result == []  # No episodes beyond index 15
        
        result = list(parse_episode_range(":20", episodes))
        assert result == episodes  # All episodes (slice stops at end)
