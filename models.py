from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'sponsor' | 'team'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pwd):
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd):
        return check_password_hash(self.password_hash, pwd)


class ResearchTeam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    field = db.Column(db.String(100))
    user = db.relationship('User', backref=db.backref('team', uselist=False))
    projects = db.relationship('Project', backref='team', lazy=True)
    responses = db.relationship('Response', backref='team', lazy=True)


class Sponsor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    company = db.Column(db.String(120))
    bio = db.Column(db.Text)
    user = db.relationship('User', backref=db.backref('sponsor', uselist=False))
    requests = db.relationship('SponsorshipRequest', backref='sponsor', lazy=True)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('research_team.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    goal = db.Column(db.Float, nullable=False)          # требуемая сумма
    raised = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='active') # active | funded | closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sponsorships = db.relationship('Sponsorship', backref='project', lazy=True)


class SponsorshipRequest(db.Model):
    """Заявка спонсора на создание/финансирование проекта.
    Научные команды могут откликаться на неё."""
    id = db.Column(db.Integer, primary_key=True)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('sponsor.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    budget = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='open')  # open | taken | closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responses = db.relationship('Response', backref='request', lazy=True)


class Response(db.Model):
    """Отклик научной команды на заявку спонсора."""
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('sponsorship_request.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('research_team.id'), nullable=False)
    pitch = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending | accepted | rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Sponsorship(db.Model):
    """Факт спонсирования проекта (создаётся после принятия отклика)."""
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('sponsor.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)