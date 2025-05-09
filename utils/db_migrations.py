import sqlite3
from flask import current_app
import os

def run_migrations():
    """Run database migrations to update schema."""
    print("Running database migrations...")
    
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
            cursor.execute("ALTER TABLE settings ADD COLUMN gitlab_url TEXT")
            conn.commit()
    except Exception as e:
        print(f"Error in migration 1: {str(e)}")
    
    # Close the connection
    conn.close()
    print("Database migrations completed")
