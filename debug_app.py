#!/usr/bin/env python3
"""
Debug script to identify startup issues
"""
import sys
import os
import traceback


def debug_imports():
    """Test all imports to find issues"""
    print("=== Testing Imports ===")

    try:
        print("✓ Testing Flask...")
        from flask import Flask
        print("✓ Flask OK")
    except Exception as e:
        print(f"✗ Flask failed: {e}")
        return False

    try:
        print("✓ Testing config...")
        from config import config
        print("✓ Config OK")
    except Exception as e:
        print(f"✗ Config failed: {e}")
        traceback.print_exc()
        return False

    try:
        print("✓ Testing extensions...")
        from extensions import db, socketio, cors
        print("✓ Extensions OK")
    except Exception as e:
        print(f"✗ Extensions failed: {e}")
        traceback.print_exc()
        return False

    try:
        print("✓ Testing models...")
        from models import Settings, Workspace
        print("✓ Models OK")
    except Exception as e:
        print(f"✗ Models failed: {e}")
        traceback.print_exc()
        return False

    try:
        print("✓ Testing blueprints...")
        from blueprints.dashboard import dashboard_bp
        print("✓ Dashboard blueprint OK")
    except Exception as e:
        print(f"✗ Dashboard blueprint failed: {e}")
        traceback.print_exc()
        return False

    return True


def debug_app_creation():
    """Test app creation"""
    print("\n=== Testing App Creation ===")

    try:
        from app import create_app
        print("✓ Importing create_app...")

        app = create_app()
        print("✓ App created successfully")

        with app.app_context():
            print("✓ App context works")

        return True
    except Exception as e:
        print(f"✗ App creation failed: {e}")
        traceback.print_exc()
        return False


def debug_database():
    """Test database connection"""
    print("\n=== Testing Database ===")

    try:
        from app import create_app
        from extensions import db

        app = create_app()
        with app.app_context():
            # Test database connection
            db.session.execute('SELECT 1')
            print("✓ Database connection OK")

            # Test table creation
            db.create_all()
            print("✓ Database tables created")

        return True
    except Exception as e:
        print(f"✗ Database failed: {e}")
        traceback.print_exc()
        return False


def main():
    print("UBRITE Workspace Manager - Debug Script")
    print("=" * 50)

    # Test imports
    if not debug_imports():
        print("\n❌ Import test failed - check dependencies")
        return 1

    # Test app creation
    if not debug_app_creation():
        print("\n❌ App creation failed - check configuration")
        return 1

    # Test database
    if not debug_database():
        print("\n❌ Database test failed - check database setup")
        return 1

    print("\n✅ All tests passed! App should start normally.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
