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
    purchases = db.relationship(
        'Sponsorship',
        backref='sponsor',
        lazy=True,
        foreign_keys='Sponsorship.sponsor_id',
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

    # --- Акции ---
    total_shares = db.Column(db.Integer, nullable=False, default=100)
    share_price = db.Column(db.Float, nullable=False, default=1.0)
    sold_shares = db.Column(db.Integer, nullable=False, default=0)

    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sponsorships = db.relationship(
        'Sponsorship',
        backref='project',
        lazy=True,
    )
    updates = db.relationship(
        'ProjectUpdate',
        backref='project',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='ProjectUpdate.created_at.desc()',
    )

    # --- Удобные свойства ---
    @property
    def goal(self):
        """Цель сбора = все акции × цена."""
        return round(self.total_shares * self.share_price, 2)

    @property
    def raised(self):
        """Собрано = проданные акции × цена."""
        return round(self.sold_shares * self.share_price, 2)

    @property
    def shares_left(self):
        return max(self.total_shares - self.sold_shares, 0)

    @property
    def progress(self):
        if self.total_shares <= 0:
            return 0
        return min(round(self.sold_shares / self.total_shares * 100), 100)


class Sponsorship(db.Model):
    """Покупка акций проекта спонсором."""

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
    shares = db.Column(db.Integer, nullable=False)      # сколько акций куплено
    amount = db.Column(db.Float, nullable=False)        # итоговая сумма
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProjectUpdate(db.Model):
    """Отчёт команды по ходу проекта."""

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey('project.id'),
        nullable=False,
    )
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)