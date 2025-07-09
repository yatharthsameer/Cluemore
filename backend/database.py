"""
Database abstraction layer for AI Interview MVP
Supports both SQLite (development) and PostgreSQL (production)
"""

import sqlite3
import logging
import os
from urllib.parse import urlparse

log = logging.getLogger("database")

# Database configuration
SQLITE_PATH = "users.db"
DATABASE_URL = os.getenv("DATABASE_URL")

# Check if we're using PostgreSQL
USE_POSTGRESQL = DATABASE_URL is not None

if USE_POSTGRESQL:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        log.info("Using PostgreSQL database")
    except ImportError:
        log.error("psycopg2 not installed but DATABASE_URL is set. Install with: pip install psycopg2-binary")
        raise
else:
    log.info(f"Using SQLite database: {SQLITE_PATH}")

class DatabaseManager:
    def __init__(self):
        if USE_POSTGRESQL:
            log.info("Database configured for PostgreSQL")
            # Parse DATABASE_URL for connection info
            parsed = urlparse(DATABASE_URL)
            self.db_config = {
                'host': parsed.hostname,
                'port': parsed.port,
                'database': parsed.path.lstrip('/'),
                'user': parsed.username,
                'password': parsed.password,
                'sslmode': 'require'  # Heroku requires SSL
            }
        else:
            log.info(f"Database configured for SQLite: {SQLITE_PATH}")

    def get_connection(self):
        """Get database connection (SQLite or PostgreSQL)"""
        if USE_POSTGRESQL:
            return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        else:
            return sqlite3.connect(SQLITE_PATH)

    def init_database(self):
        """Initialize database tables"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if USE_POSTGRESQL:
                # PostgreSQL table creation
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(255) UNIQUE NOT NULL,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE,
                        is_blocked BOOLEAN DEFAULT FALSE
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS token_usage (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        model_name VARCHAR(255) NOT NULL,
                        endpoint VARCHAR(255) NOT NULL,
                        input_tokens INTEGER DEFAULT 0,
                        output_tokens INTEGER DEFAULT 0,
                        total_tokens INTEGER NOT NULL,
                        cost_estimate DECIMAL(10,6) DEFAULT 0.0,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        request_type VARCHAR(255),
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                """)

                # Create indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_usage_user_time 
                    ON token_usage (user_id, timestamp)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_usage_model_time 
                    ON token_usage (model_name, timestamp)
                """)

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_notes (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_notes_user_id 
                    ON user_notes (user_id)
                """
                )

            else:
                # SQLite table creation
                cursor.execute("""
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
                """)

                cursor.execute("""
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
                """)

                # Create indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_usage_user_time 
                    ON token_usage (user_id, timestamp)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_usage_model_time 
                    ON token_usage (model_name, timestamp)
                """)

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_notes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_notes_user_id 
                    ON user_notes (user_id)
                """
                )

            conn.commit()
            conn.close()
            log.info("✅ Database initialized successfully")

        except Exception as e:
            log.error(f"❌ Database initialization error: {e}")
            raise

    def execute_query(self, query, params=None, fetch=False):
        """Execute a query with proper parameter binding"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if fetch:
                if fetch == 'one':
                    result = cursor.fetchone()
                    # Convert to dict for PostgreSQL compatibility
                    if result and USE_POSTGRESQL:
                        result = dict(result)
                elif fetch == 'all':
                    result = cursor.fetchall()
                    # Convert to list of dicts for PostgreSQL compatibility
                    if result and USE_POSTGRESQL:
                        result = [dict(row) for row in result]
                else:
                    result = cursor.fetchall()
                    if result and USE_POSTGRESQL:
                        result = [dict(row) for row in result]
            else:
                if USE_POSTGRESQL:
                    # PostgreSQL doesn't support lastrowid, need to handle differently
                    result = cursor.rowcount
                else:
                    result = cursor.lastrowid

            conn.commit()
            return result

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

# Global database manager instance
db_manager = DatabaseManager() 
