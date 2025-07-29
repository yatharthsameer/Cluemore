from flask import Blueprint, request, jsonify
import logging
from auth import token_required
from database import USE_POSTGRESQL, db_manager

# Create notes blueprint
notes_bp = Blueprint('notes', __name__, url_prefix='/api')

log = logging.getLogger("notes_routes")


@notes_bp.get("/notes")
@token_required
def api_get_notes(current_user):
    """Get user's notes"""
    try:
        log.info(f"Notes requested for user {current_user['id']}")

        # Get user's notes from database
        if USE_POSTGRESQL:
            query = "SELECT id, content, created_at, updated_at FROM user_notes WHERE user_id = %s ORDER BY updated_at DESC"
        else:
            query = "SELECT id, content, created_at, updated_at FROM user_notes WHERE user_id = ? ORDER BY updated_at DESC"

        notes = db_manager.execute_query(
            query,
            (current_user["id"],),
            fetch="all",
        )

        if not notes:
            # Return empty notes if none exist
            return (
                jsonify(
                    {
                        "success": True,
                        "notes": {
                            "id": None,
                            "content": "",
                            "created_at": None,
                            "updated_at": None,
                        },
                    }
                ),
                200,
            )

        # Return the most recent note (users typically have one notes document)
        latest_note = notes[0] if notes else None

        return (
            jsonify(
                {
                    "success": True,
                    "notes": {
                        "id": (
                            latest_note[0] if not USE_POSTGRESQL else latest_note["id"]
                        ),
                        "content": (
                            latest_note[1]
                            if not USE_POSTGRESQL
                            else latest_note["content"]
                        ),
                        "created_at": (
                            latest_note[2]
                            if not USE_POSTGRESQL
                            else latest_note["created_at"]
                        ),
                        "updated_at": (
                            latest_note[3]
                            if not USE_POSTGRESQL
                            else latest_note["updated_at"]
                        ),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        log.error(f"Get notes API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@notes_bp.post("/notes")
@token_required
def api_save_notes(current_user):
    """Save or update user's notes"""
    try:
        log.info(f"Notes save requested for user {current_user['id']}")

        j = request.get_json(force=True, silent=True) or {}
        content = j.get("content", "").strip()

        if not content:
            # If content is empty, delete existing notes
            if USE_POSTGRESQL:
                query = "DELETE FROM user_notes WHERE user_id = %s"
            else:
                query = "DELETE FROM user_notes WHERE user_id = ?"
            db_manager.execute_query(query, (current_user["id"],))
            return (
                jsonify({"success": True, "message": "Notes cleared successfully"}),
                200,
            )

        # Check if user already has notes
        if USE_POSTGRESQL:
            query = "SELECT id FROM user_notes WHERE user_id = %s"
        else:
            query = "SELECT id FROM user_notes WHERE user_id = ?"
        existing_notes = db_manager.execute_query(
            query,
            (current_user["id"],),
            fetch="one",
        )

        if existing_notes:
            # Update existing notes
            note_id = existing_notes[0] if not USE_POSTGRESQL else existing_notes["id"]
            if USE_POSTGRESQL:
                query = "UPDATE user_notes SET content = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
            else:
                query = "UPDATE user_notes SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            db_manager.execute_query(
                query,
                (content, note_id),
            )
            log.info(f"Notes updated for user {current_user['id']}")
        else:
            # Create new notes
            if USE_POSTGRESQL:
                query = "INSERT INTO user_notes (user_id, content) VALUES (%s, %s)"
            else:
                query = "INSERT INTO user_notes (user_id, content) VALUES (?, ?)"
            db_manager.execute_query(
                query,
                (current_user["id"], content),
            )
            log.info(f"Notes created for user {current_user['id']}")

        return jsonify({"success": True, "message": "Notes saved successfully"}), 200

    except Exception as e:
        log.error(f"Save notes API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@notes_bp.delete("/notes")
@token_required
def api_delete_notes(current_user):
    """Delete user's notes"""
    try:
        log.info(f"Notes delete requested for user {current_user['id']}")

        if USE_POSTGRESQL:
            query = "DELETE FROM user_notes WHERE user_id = %s"
        else:
            query = "DELETE FROM user_notes WHERE user_id = ?"
        
        db_manager.execute_query(query, (current_user["id"],))

        return jsonify({"success": True, "message": "Notes deleted successfully"}), 200

    except Exception as e:
        log.error(f"Delete notes API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500 