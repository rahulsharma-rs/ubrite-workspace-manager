import sqlite3
from flask import current_app
import os
import logging
from extensions import db


def run_migrations():
    """Run database migrations to update schema."""
    print("Running database migrations...")

    try:
        # First, create all tables if they don't exist
        db.create_all()

        # Get database path from SQLAlchemy URI
        db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri[10:]  # Remove 'sqlite:///' prefix
        else:
            print("Unsupported database type for migrations")
            return

        # Check if database file exists
        if not os.path.exists(db_path):
            print(f"Database file not found: {db_path}")
            return

        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Migration 1: Add gitlab_url column to settings table if it doesn't exist
        try:
            # Check if the column exists
            cursor.execute("PRAGMA table_info(settings)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'gitlab_url' not in columns:
                print("Adding gitlab_url column to settings table")
                cursor.execute("ALTER TABLE settings ADD COLUMN gitlab_url VARCHAR(255)")
                conn.commit()
        except Exception as e:
            print(f"Error in migration 1: {str(e)}")

        # Migration 2: Add git configuration columns to settings table
        git_settings_columns = [
            ('git_user_name', 'VARCHAR(255)'),
            ('git_user_email', 'VARCHAR(255)'),
            ('git_ssh_key_path', 'VARCHAR(255)'),
            ('git_signing_key', 'VARCHAR(255)'),
            ('git_default_branch', 'VARCHAR(100) DEFAULT "main"')
        ]

        for column_name, column_type in git_settings_columns:
            try:
                cursor.execute("PRAGMA table_info(settings)")
                columns = [column[1] for column in cursor.fetchall()]

                if column_name not in columns:
                    print(f"Adding {column_name} column to settings table")
                    cursor.execute(f"ALTER TABLE settings ADD COLUMN {column_name} {column_type}")
                    conn.commit()
            except Exception as e:
                print(f"Error adding {column_name} column: {str(e)}")

        # Migration 3: Add git override columns to workspace table
        git_workspace_columns = [
            ('git_user_name_override', 'VARCHAR(255)'),
            ('git_user_email_override', 'VARCHAR(255)')
        ]

        for column_name, column_type in git_workspace_columns:
            try:
                cursor.execute("PRAGMA table_info(workspace)")
                columns = [column[1] for column in cursor.fetchall()]

                if column_name not in columns:
                    print(f"Adding {column_name} column to workspace table")
                    cursor.execute(f"ALTER TABLE workspace ADD COLUMN {column_name} {column_type}")
                    conn.commit()
            except Exception as e:
                print(f"Error adding {column_name} column: {str(e)}")

        # Close the connection
        conn.close()
        print("Database migrations completed")

    except Exception as e:
        print(f"Error running migrations: {str(e)}")
        logging.error(f"Database migration error: {str(e)}")
