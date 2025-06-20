def run_migrations():
    """Run database migrations to ensure schema is up to date."""
    try:
        # Check if gitlab_url column exists in settings table
        inspector = db.inspect(db.engine)
        settings_columns = [col['name'] for col in inspector.get_columns('settings')]

        if 'gitlab_url' not in settings_columns:
            logger.info("Adding gitlab_url column to settings table")
            with db.engine.connect() as conn:
                conn.execute('ALTER TABLE settings ADD COLUMN gitlab_url VARCHAR(255)')
                conn.commit()
            logger.info("Added gitlab_url column successfully")

        # Check if git configuration columns exist
        git_columns = ['git_user_name', 'git_user_email', 'git_ssh_key_path',
                       'git_signing_key', 'git_default_branch']

        for col in git_columns:
            if col not in settings_columns:
                logger.info(f"Adding {col} column to settings table")
                with db.engine.connect() as conn:
                    if col == 'git_default_branch':
                        conn.execute(f'ALTER TABLE settings ADD COLUMN {col} VARCHAR(100) DEFAULT "main"')
                    else:
                        conn.execute(f'ALTER TABLE settings ADD COLUMN {col} VARCHAR(255)')
                    conn.commit()
                logger.info(f"Added {col} column successfully")

        # Check if workspace git override columns exist
        workspace_columns = [col['name'] for col in inspector.get_columns('workspace')]
        git_override_columns = ['git_user_name_override', 'git_user_email_override']

        for col in git_override_columns:
            if col not in workspace_columns:
                logger.info(f"Adding {col} column to workspace table")
                with db.engine.connect() as conn:
                    conn.execute(f'ALTER TABLE workspace ADD COLUMN {col} VARCHAR(255)')
                    conn.commit()
                logger.info(f"Added {col} column successfully")

        logger.info("Database migrations completed successfully")

    except Exception as e:
        logger.error(f"Error running database migrations: {str(e)}")
        # Don't fail completely, just log the error
