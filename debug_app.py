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
        from sqlalchemy import text

        app = create_app()
        with app.app_context():
            # Test database connection with proper SQLAlchemy 2.x syntax
            result = db.session.execute(text('SELECT 1'))
            print("✓ Database connection OK")

            # Test table creation
            db.create_all()
            print("✓ Database tables created")

            # Test settings table
            from models import Settings
            settings_count = Settings.query.count()
            print(f"✓ Settings table has {settings_count} records")

        return True
    except Exception as e:
        print(f"✗ Database failed: {e}")
        traceback.print_exc()
        return False


def debug_routes():
    """Test route registration"""
    print("\n=== Testing Routes ===")

    try:
        from app import create_app

        app = create_app()

        print("✓ Registered routes:")
        for rule in app.url_map.iter_rules():
            print(f"  {rule.methods} {rule.rule}")

        return True
    except Exception as e:
        print(f"✗ Route testing failed: {e}")
        traceback.print_exc()
        return False


def debug_templates():
    """Test template rendering"""
    print("\n=== Testing Templates ===")

    try:
        from app import create_app
        from flask import render_template_string

        app = create_app()

        with app.app_context():
            # Test basic template rendering
            test_html = render_template_string("<h1>Test</h1>")
            print("✓ Basic template rendering works")

            # Test if dashboard template exists
            try:
                with open('templates/dashboard.html', 'r') as f:
                    content = f.read()
                    if 'UBRITEAPIClient' in content:
                        print("✓ Dashboard template found")
                    else:
                        print("⚠ Dashboard template missing API client")
            except FileNotFoundError:
                print("✗ Dashboard template not found")
                return False

        return True
    except Exception as e:
        print(f"✗ Template testing failed: {e}")
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

    # Test routes
    if not debug_routes():
        print("\n❌ Route test failed - check blueprints")
        return 1

    # Test templates
    if not debug_templates():
        print("\n❌ Template test failed - check templates")
        return 1

    print("\n✅ All tests passed! App should start normally.")
    print("\n🔧 If you're still getting 'Incomplete response', try:")
    print("1. Check specific route: /health")
    print("2. Check browser console for JavaScript errors")
    print("3. Check OnDemand logs for runtime errors")
    return 0


if __name__ == '__main__':
    sys.exit(main())
