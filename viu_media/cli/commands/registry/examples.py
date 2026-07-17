"""
Example usage for the registry command
"""

main = """

Examples:
  # Sync with remote AniList
  ani-browse registry sync --upload --download

  # Show detailed registry statistics  
  ani-browse registry stats --detailed

  # Search local registry
  ani-browse registry search "attack on titan"

  # Export registry to JSON
  ani-browse registry export --format json --output backup.json

  # Import from backup
  ani-browse registry import backup.json

  # Clean up orphaned entries
  ani-browse registry clean --dry-run

  # Create full backup
  ani-browse registry backup --compress

  # Restore from backup
  ani-browse registry restore backup.tar.gz
"""
