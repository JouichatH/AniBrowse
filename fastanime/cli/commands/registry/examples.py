"""
Example usage for the registry command
"""

main = """

Examples:
  # Sync with remote AniList
  fastanime registry sync --upload --download

  # Show detailed registry statistics  
  fastanime registry stats --detailed

  # Search local registry
  fastanime registry search "attack on titan"

  # Export registry to JSON
  fastanime registry export --format json --output backup.json

  # Import from backup
  fastanime registry import backup.json

  # Clean up orphaned entries
  fastanime registry clean --dry-run

  # Create full backup
  fastanime registry backup --compress

  # Restore from backup
  fastanime registry restore backup.tar.gz
"""
