from flask import Blueprint, request, jsonify
import logging
from auth import auth_manager, token_required

# Create auth blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

log = logging.getLogger("auth_routes")

@auth_bp.post("/register")
def api_register():
    """Register a new user"""
    try:
        log.info("=== User Registration API called ===")
        j = request.get_json(force=True, silent=True) or {}

        email = j.get("email", "").strip()
        password = j.get("password", "").strip()

        log.info(f"Registration attempt for email: {email}")

        # Register user
        result = auth_manager.register_user(email, password)

        if result["success"]:
            log.info(f"User {email} registered successfully")
            return jsonify(result), 200
        else:
            log.warning(f"Registration failed for {email}: {result['error']}")
            return jsonify(result), 400

    except Exception as e:
        log.error(f"Registration API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@auth_bp.post("/login")
def api_login():
    """Login a user"""
    try:
        log.info("=== User Login API called ===")
        j = request.get_json(force=True, silent=True) or {}

        email = j.get("email", "").strip()
        password = j.get("password", "").strip()

        log.info(f"Login attempt for: {email}")

        # Login user
        result = auth_manager.login_user(email, password)

        if result["success"]:
            log.info(f"User {email} logged in successfully")
            return jsonify(result), 200
        else:
            log.warning(f"Login failed for {email}: {result['error']}")
            return jsonify(result), 401

    except Exception as e:
        log.error(f"Login API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@auth_bp.post("/verify")
def api_verify_token():
    """Verify a JWT token and return user info"""
    try:
        log.info("=== Token Verification API called ===")
        j = request.get_json(force=True, silent=True) or {}

        token = j.get("token", "").strip()

        if not token:
            return jsonify({"success": False, "error": "Token is required"}), 400

        # Verify token and get user
        user = auth_manager.get_user_from_token(token)

        if user:
            log.info(f"Token verified for user: {user['email']}")
            return jsonify({"success": True, "user": user, "valid": True}), 200
        else:
            log.warning("Token verification failed")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid token",
                        "valid": False,
                    }
                ),
                401,
            )

    except Exception as e:
        log.error(f"Token verification API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@auth_bp.get("/me")
@token_required
def api_get_current_user(current_user):
    """Get current user info (requires authentication)"""
    try:
        log.info(f"Getting current user info for: {current_user['email']}")
        return jsonify({"success": True, "user": current_user}), 200

    except Exception as e:
        log.error(f"Get current user API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500 