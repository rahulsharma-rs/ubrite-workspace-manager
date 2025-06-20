from extensions import db
from datetime import datetime
import json


class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    gitlab_pat_encrypted = db.Column(db.LargeBinary)
    gitlab_url = db.Column(db.String(255))
    encryption_key = db.Column(db.LargeBinary)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    # Git user configuration
    git_user_name = db.Column(db.String(255))
    git_user_email = db.Column(db.String(255))
    git_ssh_key_path = db.Column(db.String(255))
    git_signing_key = db.Column(db.String(255))
    git_default_branch = db.Column(db.String(100), default='main')


class Workspace(db.Model):
    __tablename__ = 'workspace'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    path = db.Column(db.String(255), nullable=False)
    db_path = db.Column(db.String(255), nullable=False)
    gitlab_repo_id = db.Column(db.Integer)
    gitlab_repo_url = db.Column(db.String(255))
    env_type = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)
    # Workspace-specific git configuration (optional overrides)
    git_user_name_override = db.Column(db.String(255))
    git_user_email_override = db.Column(db.String(255))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'path': self.path,
            'db_path': self.db_path,
            'gitlab_repo_id': self.gitlab_repo_id,
            'gitlab_repo_url': self.gitlab_repo_url,
            'env_type': self.env_type,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'git_user_name_override': self.git_user_name_override,
            'git_user_email_override': self.git_user_email_override
        }


class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'))
    event_type = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    workspace = db.relationship('Workspace', backref=db.backref('audit_logs', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'event_type': self.event_type,
            'details': json.loads(self.details) if self.details else {},
            'timestamp': self.timestamp.isoformat()
        }
