"""
Database abstraction layer for AI Interview MVP
Uses SQLite for simple setup and portability
"""

import sqlite3
import logging

log = logging.getLogger("database")

# SQLite database path
SQLITE_PATH = "users.db"


class DatabaseManager:
    def __init__(self):
        log.info(f"Using SQLite database: {SQLITE_PATH}")

    def get_connection(self):
        """Get SQLite database connection"""
        return sqlite3.connect(SQLITE_PATH)

    def init_database(self):
        """Initialize database tables"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Create users table
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

            # Create token usage table
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

            # Add is_blocked column if it doesn't exist (migration)
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN is_blocked BOOLEAN DEFAULT 0")
            except sqlite3.OperationalError:
                # Column already exists
                pass

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
                elif fetch == 'all':
                    result = cursor.fetchall()
                else:
                    result = cursor.fetchall()
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