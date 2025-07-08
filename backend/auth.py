

import sqlite3
import bcrypt
import jwt
import json
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError(
        "JWT_SECRET environment variable is required. Please add it to your .env file."
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Database file path
DB_PATH = "users.db"


class AuthManager:
    def __init__(self):
        self.init_database()

    def init_database(self):
        """Initialize the SQLite database with users table"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Create users table if it doesn't exist
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    is_blocked BOOLEAN DEFAULT 0
                )
            """
            )

            # Create token_usage table for tracking API usage
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER NOT NULL,
                    cost_estimate REAL DEFAULT 0.0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    request_type TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """
            )

            # Create index for faster queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_token_usage_user_time 
                ON token_usage (user_id, timestamp)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_token_usage_model_time 
                ON token_usage (model_name, timestamp)
            """
            )

            # Add is_blocked column to existing users table if it doesn't exist
            try:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN is_blocked BOOLEAN DEFAULT 0"
                )
            except sqlite3.OperationalError:
                # Column already exists
                pass

            conn.commit()
            conn.close()
            print("✅ Database initialized successfully")

        except Exception as e:
            print(f"❌ Database initialization error: {e}")

    def hash_password(self, password):
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, password, password_hash):
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

    def generate_jwt_token(self, user_id, email):
        """Generate a JWT token for a user"""
        payload = {
            "user_id": user_id,
            "email": email,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def verify_jwt_token(self, token):
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def register_user(self, email, password):
        """Register a new user"""
        try:
            # Validate input
            if not email or not password:
                return {"success": False, "error": "Email and password are required"}

            if len(password) < 6:
                return {
                    "success": False,
                    "error": "Password must be at least 6 characters",
                }

            # Check if user already exists
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM users WHERE email = ?",
                (email,),
            )
            existing_user = cursor.fetchone()

            if existing_user:
                conn.close()
                return {"success": False, "error": "Email already exists"}

            # Hash password and create user
            password_hash = self.hash_password(password)

            # Use email as username for backward compatibility
            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (?, ?, ?)
            """,
                (email, email, password_hash),
            )

            user_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Generate JWT token
            token = self.generate_jwt_token(user_id, email)

            return {
                "success": True,
                "token": token,
                "user": {"id": user_id, "email": email},
            }

        except Exception as e:
            return {"success": False, "error": f"Registration failed: {str(e)}"}

    def login_user(self, email, password):
        """Login a user"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Find user by email
            cursor.execute(
                """
                SELECT id, username, email, password_hash, is_active 
                FROM users 
                WHERE email = ? AND is_active = 1
            """,
                (email,),
            )

            user = cursor.fetchone()

            if not user:
                conn.close()
                return {"success": False, "error": "Invalid email or password"}

            user_id, user_username, email, password_hash, is_active = user

            # Verify password
            if not self.verify_password(password, password_hash):
                conn.close()
                return {"success": False, "error": "Invalid email or password"}

            # Update last login
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user_id,),
            )
            conn.commit()
            conn.close()

            # Generate JWT token
            token = self.generate_jwt_token(user_id, email)

            return {
                "success": True,
                "token": token,
                "user": {"id": user_id, "email": email},
            }

        except Exception as e:
            return {"success": False, "error": f"Login failed: {str(e)}"}

    def get_user_from_token(self, token):
        """Get user information from JWT token"""
        try:
            payload = self.verify_jwt_token(token)
            if not payload:
                return None

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, username, email, is_active, is_blocked 
                FROM users 
                WHERE id = ? AND is_active = 1
            """,
                (payload["user_id"],),
            )

            user = cursor.fetchone()
            conn.close()

            if user:
                user_id, username, email, is_active, is_blocked = user

                # Check if user is blocked
                if is_blocked:
                    return None

                return {
                    "id": user_id,
                    "email": email,
                    "is_active": is_active,
                    "is_blocked": is_blocked,
                }
            return None

        except Exception as e:
            print(f"Error getting user from token: {e}")
            return None

    def log_token_usage(
        self,
        user_id,
        model_name,
        endpoint,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        cost_estimate=0.0,
        request_type=None,
    ):
        """Log token usage for a user"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO token_usage 
                (user_id, model_name, endpoint, input_tokens, output_tokens, total_tokens, cost_estimate, request_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    model_name,
                    endpoint,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    cost_estimate,
                    request_type,
                ),
            )

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error logging token usage: {e}")
            return False

    def get_user_token_usage(self, user_id, days=30):
        """Get token usage for a specific user over the last N days"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT model_name, endpoint, SUM(total_tokens) as total_tokens, 
                       SUM(cost_estimate) as total_cost, COUNT(*) as request_count,
                       MIN(timestamp) as first_request, MAX(timestamp) as last_request
                FROM token_usage 
                WHERE user_id = ? AND timestamp >= datetime('now', '-{} days')
                GROUP BY model_name, endpoint
                ORDER BY total_tokens DESC
            """.format(
                    days
                ),
                (user_id,),
            )

            results = cursor.fetchall()
            conn.close()

            usage_data = []
            for row in results:
                usage_data.append(
                    {
                        "model_name": row[0],
                        "endpoint": row[1],
                        "total_tokens": row[2],
                        "total_cost": row[3],
                        "request_count": row[4],
                        "first_request": row[5],
                        "last_request": row[6],
                    }
                )

            return usage_data

        except Exception as e:
            print(f"Error getting user token usage: {e}")
            return []

    def get_all_users_usage_summary(self, days=30):
        """Get token usage summary for all users"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT u.id, u.email, u.is_blocked,
                       COALESCE(SUM(t.total_tokens), 0) as total_tokens,
                       COALESCE(SUM(t.cost_estimate), 0) as total_cost,
                       COALESCE(COUNT(t.id), 0) as request_count
                FROM users u
                LEFT JOIN token_usage t ON u.id = t.user_id 
                    AND t.timestamp >= datetime('now', '-{} days')
                WHERE u.is_active = 1
                GROUP BY u.id, u.email, u.is_blocked
                ORDER BY total_tokens DESC
            """.format(
                    days
                )
            )

            results = cursor.fetchall()
            conn.close()

            users_usage = []
            for row in results:
                users_usage.append(
                    {
                        "user_id": row[0],
                        "email": row[1],
                        "is_blocked": bool(row[2]),
                        "total_tokens": row[3],
                        "total_cost": row[4],
                        "request_count": row[5],
                    }
                )

            return users_usage

        except Exception as e:
            print(f"Error getting all users usage summary: {e}")
            return []

    def block_user(self, user_id):
        """Block a user from using the service"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute("UPDATE users SET is_blocked = 1 WHERE id = ?", (user_id,))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error blocking user: {e}")
            return False

    def unblock_user(self, user_id):
        """Unblock a user"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute("UPDATE users SET is_blocked = 0 WHERE id = ?", (user_id,))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error unblocking user: {e}")
            return False


# Global auth manager instance
auth_manager = AuthManager()


def token_required(f):
    """Decorator to require authentication for API endpoints"""

    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Get token from Authorization header
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            try:
                token = auth_header.split(" ")[1]  # Bearer TOKEN
            except IndexError:
                return jsonify({"error": "Invalid token format"}), 401

        if not token:
            return jsonify({"error": "Token is missing"}), 401

        # Verify token and get user
        user = auth_manager.get_user_from_token(token)
        if not user:
            return jsonify({"error": "Token is invalid or expired"}), 401

        # Add user to request context and pass as parameter
        request.current_user = user
        return f(user, *args, **kwargs)

    return decorated
