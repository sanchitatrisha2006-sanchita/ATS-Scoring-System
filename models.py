"""
Database Models
----------------
Uses SQLAlchemy ORM with SQLite.
Two tables: User (for login/signup) and ScoreRecord (history of resume scores).
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    records = db.relationship("ScoreRecord", backref="user", lazy=True)


class ScoreRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    resume_filename = db.Column(db.String(255))
    job_title = db.Column(db.String(255))
    score = db.Column(db.Float, nullable=False)
    missing_keywords = db.Column(db.Text)  # stored as comma-separated string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
