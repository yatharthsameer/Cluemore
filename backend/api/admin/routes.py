from flask import Blueprint, request, jsonify
import logging
from auth import auth_manager
from token_tracker import token_tracker

# Create admin blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

log = logging.getLogger("admin_routes")


@admin_bp.get("/users")
def api_admin_get_users():
    """Get all users with their token usage summary (no auth required for simplicity)"""
    try:
        log.info("Admin users list requested")

        days = request.args.get("days", 30, type=int)
        users_usage = auth_manager.get_all_users_usage_summary(days)

        return (
            jsonify({"success": True, "users": users_usage, "period_days": days}),
            200,
        )

    except Exception as e:
        log.error(f"Admin users API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@admin_bp.get("/user/<int:user_id>/usage")
def api_admin_get_user_usage(user_id):
    """Get detailed usage for a specific user"""
    try:
        log.info(f"User {user_id} usage requested")

        days = request.args.get("days", 30, type=int)
        usage_data = auth_manager.get_user_token_usage(user_id, days)

        # Get user limits
        limits = token_tracker.check_user_limits(user_id)

        return (
            jsonify(
                {
                    "success": True,
                    "user_id": user_id,
                    "usage": usage_data,
                    "limits": limits,
                    "period_days": days,
                }
            ),
            200,
        )

    except Exception as e:
        log.error(f"Admin user usage API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@admin_bp.post("/user/<int:user_id>/block")
def api_admin_block_user(user_id):
    """Block a user from using the service"""
    try:
        log.info(f"User {user_id} block requested")

        success = auth_manager.block_user(user_id)

        if success:
            log.info(f"User {user_id} blocked successfully")
            return (
                jsonify({"success": True, "message": "User blocked successfully"}),
                200,
            )
        else:
            return jsonify({"success": False, "error": "Failed to block user"}), 500

    except Exception as e:
        log.error(f"Admin block user API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@admin_bp.post("/user/<int:user_id>/unblock")
def api_admin_unblock_user(user_id):
    """Unblock a user"""
    try:
        log.info(f"User {user_id} unblock requested")

        success = auth_manager.unblock_user(user_id)

        if success:
            log.info(f"User {user_id} unblocked successfully")
            return (
                jsonify({"success": True, "message": "User unblocked successfully"}),
                200,
            )
        else:
            return jsonify({"success": False, "error": "Failed to unblock user"}), 500

    except Exception as e:
        log.error(f"Admin unblock user API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@admin_bp.get("/stats")
def api_admin_get_stats():
    """Get overall system statistics"""
    try:
        log.info("Admin stats requested")
        from database import USE_POSTGRESQL, db_manager

        # Get basic stats from database using database manager
        # Total users
        total_users = (
            db_manager.execute_query(
                "SELECT COUNT(*) FROM users WHERE is_active = TRUE", fetch="one"
            )[0]
            if not USE_POSTGRESQL
            else db_manager.execute_query(
                "SELECT COUNT(*) FROM users WHERE is_active = TRUE", fetch="one"
            )["count"]
        )

        # Blocked users
        blocked_users = (
            db_manager.execute_query(
                "SELECT COUNT(*) FROM users WHERE is_active = TRUE AND is_blocked = TRUE",
                fetch="one",
            )[0]
            if not USE_POSTGRESQL
            else db_manager.execute_query(
                "SELECT COUNT(*) FROM users WHERE is_active = TRUE AND is_blocked = TRUE",
                fetch="one",
            )["count"]
        )

        # Total API calls in last 24 hours
        if USE_POSTGRESQL:
            query = "SELECT COUNT(*) FROM token_usage WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24 hours'"
        else:
            query = "SELECT COUNT(*) FROM token_usage WHERE timestamp >= datetime('now', '-24 hours')"

        api_calls_24h = (
            db_manager.execute_query(query, fetch="one")[0]
            if not USE_POSTGRESQL
            else db_manager.execute_query(query, fetch="one")["count"]
        )

        # Total tokens used in last 24 hours
        if USE_POSTGRESQL:
            query = "SELECT COALESCE(SUM(total_tokens), 0) FROM token_usage WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24 hours'"
        else:
            query = "SELECT COALESCE(SUM(total_tokens), 0) FROM token_usage WHERE timestamp >= datetime('now', '-24 hours')"

        tokens_24h = (
            db_manager.execute_query(query, fetch="one")[0]
            if not USE_POSTGRESQL
            else db_manager.execute_query(query, fetch="one")["coalesce"]
        )

        # Cost in last 24 hours
        if USE_POSTGRESQL:
            query = "SELECT COALESCE(SUM(cost_estimate), 0.0) FROM token_usage WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24 hours'"
        else:
            query = "SELECT COALESCE(SUM(cost_estimate), 0.0) FROM token_usage WHERE timestamp >= datetime('now', '-24 hours')"

        cost_24h = (
            db_manager.execute_query(query, fetch="one")[0]
            if not USE_POSTGRESQL
            else db_manager.execute_query(query, fetch="one")["coalesce"]
        )

        # Most used models
        if USE_POSTGRESQL:
            query = """
                SELECT model_name, COUNT(*) as count 
                FROM token_usage 
                WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '7 days'
                GROUP BY model_name 
                ORDER BY count DESC 
                LIMIT 5
            """
        else:
            query = """
                SELECT model_name, COUNT(*) as count 
                FROM token_usage 
                WHERE timestamp >= datetime('now', '-7 days')
                GROUP BY model_name 
                ORDER BY count DESC 
                LIMIT 5
            """

        popular_models = db_manager.execute_query(query, fetch="all")

        # Format popular models for response
        models_list = []
        if popular_models:
            for model in popular_models:
                if USE_POSTGRESQL:
                    models_list.append({
                        "model": model["model_name"],
                        "usage_count": model["count"]
                    })
                else:
                    models_list.append({
                        "model": model[0],
                        "usage_count": model[1]
                    })

        return (
            jsonify(
                {
                    "success": True,
                    "stats": {
                        "total_users": total_users or 0,
                        "blocked_users": blocked_users or 0,
                        "api_calls_24h": api_calls_24h or 0,
                        "tokens_used_24h": tokens_24h or 0,
                        "cost_24h": float(cost_24h or 0.0),
                        "popular_models": models_list,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        log.error(f"Admin stats API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500 