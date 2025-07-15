"""
Session state management utilities for the interactive CLI.
Provides comprehensive session save/resume functionality with error handling and metadata.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ....core.constants import APP_DATA_DIR
from ...interactive.state import State

logger = logging.getLogger(__name__)

# Session storage directory
SESSIONS_DIR =  APP_DATA_DIR / "sessions"
AUTO_SAVE_FILE = SESSIONS_DIR / "auto_save.json"
CRASH_BACKUP_FILE = SESSIONS_DIR / "crash_backup.json"


class SessionMetadata:
    """Metadata for saved sessions."""
    
    def __init__(
        self,
        created_at: Optional[datetime] = None,
        last_saved: Optional[datetime] = None,
        session_name: Optional[str] = None,
        description: Optional[str] = None,
        state_count: int = 0
    ):
        self.created_at = created_at or datetime.now()
        self.last_saved = last_saved or datetime.now()
        self.session_name = session_name
        self.description = description
        self.state_count = state_count
    
    def to_dict(self) -> dict:
        """Convert metadata to dictionary for JSON serialization."""
        return {
            "created_at": self.created_at.isoformat(),
            "last_saved": self.last_saved.isoformat(),
            "session_name": self.session_name,
            "description": self.description,
            "state_count": self.state_count
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionMetadata":
        """Create metadata from dictionary."""
        return cls(
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            last_saved=datetime.fromisoformat(data.get("last_saved", datetime.now().isoformat())),
            session_name=data.get("session_name"),
            description=data.get("description"),
            state_count=data.get("state_count", 0)
        )


class SessionData:
    """Complete session data including history and metadata."""
    
    def __init__(self, history: List[State], metadata: SessionMetadata):
        self.history = history
        self.metadata = metadata
    
    def to_dict(self) -> dict:
        """Convert session data to dictionary for JSON serialization."""
        return {
            "metadata": self.metadata.to_dict(),
            "history": [state.model_dump(mode="json") for state in self.history],
            "format_version": "1.0"  # For future compatibility
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionData":
        """Create session data from dictionary."""
        metadata = SessionMetadata.from_dict(data.get("metadata", {}))
        history_data = data.get("history", [])
        history = []
        
        for state_dict in history_data:
            try:
                state = State.model_validate(state_dict)
                history.append(state)
            except Exception as e:
                logger.warning(f"Skipping invalid state in session: {e}")
        
        return cls(history, metadata)


class SessionManager:
    """Manages session save/resume functionality with comprehensive error handling."""
    
    def __init__(self):
        self._ensure_sessions_directory()
    
    def _ensure_sessions_directory(self):
        """Ensure the sessions directory exists."""
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    def save_session(
        self, 
        history: List[State], 
        file_path: Path,
        session_name: Optional[str] = None,
        description: Optional[str] = None,
        feedback=None
    ) -> bool:
        """
        Save session history to a JSON file with metadata.
        
        Args:
            history: List of session states
            file_path: Path to save the session
            session_name: Optional name for the session
            description: Optional description
            feedback: Optional feedback manager for user notifications
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create metadata
            metadata = SessionMetadata(
                session_name=session_name,
                description=description,
                state_count=len(history)
            )
            
            # Create session data
            session_data = SessionData(history, metadata)
            
            # Save to file
            with file_path.open('w', encoding='utf-8') as f:
                json.dump(session_data.to_dict(), f, indent=2, ensure_ascii=False)
            
            if feedback:
                feedback.success(
                    "Session saved successfully",
                    f"Saved {len(history)} states to {file_path.name}"
                )
            
            logger.info(f"Session saved to {file_path} with {len(history)} states")
            return True
            
        except Exception as e:
            error_msg = f"Failed to save session: {e}"
            if feedback:
                feedback.error("Failed to save session", str(e))
            logger.error(error_msg)
            return False
    
    def load_session(self, file_path: Path, feedback=None) -> Optional[List[State]]:
        """
        Load session history from a JSON file.
        
        Args:
            file_path: Path to the session file
            feedback: Optional feedback manager for user notifications
            
        Returns:
            List of states if successful, None otherwise
        """
        if not file_path.exists():
            if feedback:
                feedback.warning(
                    "Session file not found",
                    f"The file {file_path.name} does not exist"
                )
            logger.warning(f"Session file not found: {file_path}")
            return None
        
        try:
            with file_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            session_data = SessionData.from_dict(data)
            
            if feedback:
                feedback.success(
                    "Session loaded successfully",
                    f"Loaded {len(session_data.history)} states from {file_path.name}"
                )
            
            logger.info(f"Session loaded from {file_path} with {len(session_data.history)} states")
            return session_data.history
            
        except json.JSONDecodeError as e:
            error_msg = f"Session file is corrupted: {e}"
            if feedback:
                feedback.error("Session file is corrupted", str(e))
            logger.error(error_msg)
            return None
        except Exception as e:
            error_msg = f"Failed to load session: {e}"
            if feedback:
                feedback.error("Failed to load session", str(e))
            logger.error(error_msg)
            return None
    
    def auto_save_session(self, history: List[State]) -> bool:
        """
        Auto-save session for crash recovery.
        
        Args:
            history: Current session history
            
        Returns:
            True if successful, False otherwise
        """
        return self.save_session(
            history,
            AUTO_SAVE_FILE,
            session_name="Auto Save",
            description="Automatically saved session"
        )
    
    def create_crash_backup(self, history: List[State]) -> bool:
        """
        Create a crash backup of the current session.
        
        Args:
            history: Current session history
            
        Returns:
            True if successful, False otherwise
        """
        return self.save_session(
            history,
            CRASH_BACKUP_FILE,
            session_name="Crash Backup",
            description="Session backup created before potential crash"
        )
    
    def has_auto_save(self) -> bool:
        """Check if an auto-save file exists."""
        return AUTO_SAVE_FILE.exists()
    
    def has_crash_backup(self) -> bool:
        """Check if a crash backup file exists."""
        return CRASH_BACKUP_FILE.exists()
    
    def load_auto_save(self, feedback=None) -> Optional[List[State]]:
        """Load the auto-save session."""
        return self.load_session(AUTO_SAVE_FILE, feedback)
    
    def load_crash_backup(self, feedback=None) -> Optional[List[State]]:
        """Load the crash backup session."""
        return self.load_session(CRASH_BACKUP_FILE, feedback)
    
    def clear_auto_save(self) -> bool:
        """Clear the auto-save file."""
        try:
            if AUTO_SAVE_FILE.exists():
                AUTO_SAVE_FILE.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to clear auto-save: {e}")
            return False
    
    def clear_crash_backup(self) -> bool:
        """Clear the crash backup file."""
        try:
            if CRASH_BACKUP_FILE.exists():
                CRASH_BACKUP_FILE.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to clear crash backup: {e}")
            return False
    
    def list_saved_sessions(self) -> List[Dict[str, str]]:
        """
        List all saved session files with their metadata.
        
        Returns:
            List of dictionaries containing session information
        """
        sessions = []
        
        for session_file in SESSIONS_DIR.glob("*.json"):
            if session_file.name in ["auto_save.json", "crash_backup.json"]:
                continue
                
            try:
                with session_file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                
                metadata = data.get("metadata", {})
                sessions.append({
                    "file": session_file.name,
                    "path": str(session_file),
                    "name": metadata.get("session_name", "Unnamed"),
                    "description": metadata.get("description", "No description"),
                    "created": metadata.get("created_at", "Unknown"),
                    "last_saved": metadata.get("last_saved", "Unknown"),
                    "state_count": metadata.get("state_count", 0)
                })
            except Exception as e:
                logger.warning(f"Failed to read session metadata from {session_file}: {e}")
        
        # Sort by last saved time (newest first)
        sessions.sort(key=lambda x: x["last_saved"], reverse=True)
        return sessions
    
    def cleanup_old_sessions(self, max_sessions: int = 10) -> int:
        """
        Clean up old session files, keeping only the most recent ones.
        
        Args:
            max_sessions: Maximum number of sessions to keep
            
        Returns:
            Number of sessions deleted
        """
        sessions = self.list_saved_sessions()
        
        if len(sessions) <= max_sessions:
            return 0
        
        deleted_count = 0
        sessions_to_delete = sessions[max_sessions:]
        
        for session in sessions_to_delete:
            try:
                Path(session["path"]).unlink()
                deleted_count += 1
                logger.info(f"Deleted old session: {session['name']}")
            except Exception as e:
                logger.error(f"Failed to delete session {session['name']}: {e}")
        
        return deleted_count
