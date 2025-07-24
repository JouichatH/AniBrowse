def time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS to seconds."""
    try:
        parts = time_str.split(":")
        if len(parts) == 3:
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
    except (ValueError, AttributeError):
        pass
    return 0
