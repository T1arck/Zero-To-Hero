from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # sponsor или team
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class ResearchTeam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        unique=True,
        nullable=False,
    )
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    field = db.Column(db.String(100))

    user = db.relationship(
        'User',
        backref=db.backref('team', uselist=False),
    )
    projects = db.relationship('Project', backref='team', lazy=True)
    responses = db.relationship('Response', backref='team', lazy=True)


class Sponsor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        unique=True,
        nullable=False,
    )
    company = db.Column(db.String(120))
    bio = db.Column(db.Text)

    user = db.relationship(
        'User',
        backref=db.backref('sponsor', uselist=False),
    )
    requests = db.relationship(
        'SponsorshipRequest',
        backref='sponsor',
        lazy=True,
    )


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(
        db.Integer,
        db.ForeignKey('research_team.id'),
        nullable=False,
    )
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    goal = db.Column(db.Float, nullable=False)
    raised = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sponsorships = db.relationship(
        'Sponsorship',
        backref='project',
        lazy=True,
    )


class SponsorshipRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sponsor_id = db.Column(
        db.Integer,
        db.ForeignKey('sponsor.id'),
        nullable=False,
    )
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    budget = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    responses = db.relationship(
        'Response',
        backref='request',
        lazy=True,
    )


class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer,
        db.ForeignKey('sponsorship_request.id'),
        nullable=False,
    )
    team_id = db.Column(
        db.Integer,
        db.ForeignKey('research_team.id'),
        nullable=False,
    )
    pitch = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Sponsorship(db.Model):
    """Пожертвование спонсора проекту."""

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey('project.id'),
        nullable=False,
    )
    sponsor_id = db.Column(
        db.Integer,
        db.ForeignKey('sponsor.id'),
        nullable=False,
    )
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sponsor = db.relationship('Sponsor')