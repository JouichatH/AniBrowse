"""
Test script to verify the session management system works correctly.
This tests session save/resume functionality and crash recovery.
"""
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Add the project root to the path so we can import fastanime modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastanime.cli.utils.session_manager import SessionManager, SessionMetadata, SessionData
from fastanime.cli.utils.feedback import create_feedback_manager
from fastanime.cli.interactive.state import State, MediaApiState


def test_session_management():
    """Test the session management system."""
    print("=== Testing Session Management System ===\n")
    
    feedback = create_feedback_manager(icons_enabled=True)
    session_manager = SessionManager()
    
    # Create test session states
    test_states = [
        State(menu_name="MAIN"),
        State(menu_name="RESULTS", media_api=MediaApiState()),
        State(menu_name="MEDIA_ACTIONS", media_api=MediaApiState())
    ]
    
    print("1. Testing session metadata creation:")
    metadata = SessionMetadata(
        session_name="Test Session",
        description="This is a test session for validation",
        state_count=len(test_states)
    )
    print(f"   Metadata: {metadata.session_name} - {metadata.description}")
    print(f"   States: {metadata.state_count}, Created: {metadata.created_at}")
    
    print("\n2. Testing session data serialization:")
    session_data = SessionData(test_states, metadata)
    data_dict = session_data.to_dict()
    print(f"   Serialized keys: {list(data_dict.keys())}")
    print(f"   Format version: {data_dict['format_version']}")
    
    print("\n3. Testing session data deserialization:")
    restored_session = SessionData.from_dict(data_dict)
    print(f"   Restored states: {len(restored_session.history)}")
    print(f"   Restored metadata: {restored_session.metadata.session_name}")
    
    print("\n4. Testing session save:")
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = Path(temp_dir) / "test_session.json"
        success = session_manager.save_session(
            test_states,
            test_file,
            session_name="Test Session Save",
            description="Testing save functionality",
            feedback=feedback
        )
        print(f"   Save success: {success}")
        print(f"   File exists: {test_file.exists()}")
        
        if test_file.exists():
            print(f"   File size: {test_file.stat().st_size} bytes")
            
            print("\n5. Testing session load:")
            loaded_states = session_manager.load_session(test_file, feedback)
            if loaded_states:
                print(f"   Loaded states: {len(loaded_states)}")
                print(f"   First state menu: {loaded_states[0].menu_name}")
                print(f"   Last state menu: {loaded_states[-1].menu_name}")
            
            print("\n6. Testing session file content:")
            with open(test_file, 'r') as f:
                file_content = json.load(f)
            print(f"   JSON keys: {list(file_content.keys())}")
            print(f"   History length: {len(file_content['history'])}")
            print(f"   Session name: {file_content['metadata']['session_name']}")
    
    print("\n7. Testing auto-save functionality:")
    auto_save_success = session_manager.auto_save_session(test_states)
    print(f"   Auto-save success: {auto_save_success}")
    print(f"   Has auto-save: {session_manager.has_auto_save()}")
    
    print("\n8. Testing crash backup:")
    crash_backup_success = session_manager.create_crash_backup(test_states)
    print(f"   Crash backup success: {crash_backup_success}")
    print(f"   Has crash backup: {session_manager.has_crash_backup()}")
    
    print("\n9. Testing session listing:")
    saved_sessions = session_manager.list_saved_sessions()
    print(f"   Found {len(saved_sessions)} saved sessions")
    for i, sess in enumerate(saved_sessions[:3]):  # Show first 3
        print(f"   Session {i+1}: {sess['name']} ({sess['state_count']} states)")
    
    print("\n10. Testing cleanup functions:")
    print(f"   Can clear auto-save: {session_manager.clear_auto_save()}")
    print(f"   Can clear crash backup: {session_manager.clear_crash_backup()}")
    print(f"   Auto-save exists after clear: {session_manager.has_auto_save()}")
    print(f"   Crash backup exists after clear: {session_manager.has_crash_backup()}")
    
    print("\n=== Session Management Tests Completed! ===")


def test_session_error_handling():
    """Test error handling in session management."""
    print("\n=== Testing Error Handling ===\n")
    
    feedback = create_feedback_manager(icons_enabled=True)
    session_manager = SessionManager()
    
    print("1. Testing load of non-existent file:")
    non_existent = Path("/tmp/non_existent_session.json")
    result = session_manager.load_session(non_existent, feedback)
    print(f"   Result for non-existent file: {result}")
    
    print("\n2. Testing load of corrupted file:")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json content }")
        corrupted_file = Path(f.name)
    
    try:
        result = session_manager.load_session(corrupted_file, feedback)
        print(f"   Result for corrupted file: {result}")
    finally:
        corrupted_file.unlink()  # Clean up
    
    print("\n3. Testing save to read-only location:")
    readonly_path = Path("/tmp/readonly_session.json")
    # This test would need actual readonly permissions to be meaningful
    print("   Skipped - requires permission setup")
    
    print("\n=== Error Handling Tests Completed! ===")


if __name__ == "__main__":
    test_session_management()
    test_session_error_handling()
