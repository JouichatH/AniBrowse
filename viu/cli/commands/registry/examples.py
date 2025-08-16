"""
Example usage for the registry command
"""

main = """

Examples:
  # Sync with remote AniList
  viu registry sync --upload --download

  # Show detailed registry statistics  
  viu registry stats --detailed

  # Search local registry
  viu registry search "attack on titan"

  # Export registry to JSON
  viu registry export --format json --output backup.json

  # Import from backup
  viu registry import backup.json

  # Clean up orphaned entries
  viu registry clean --dry-run

  # Create full backup
  viu registry backup --compress

  # Restore from backup
  viu registry restore backup.tar.gz
"""
