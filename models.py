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
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class ResearchTeam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    field = db.Column(db.String(100))

    user = db.relationship('User', backref=db.backref('team', uselist=False))
    projects = db.relationship('Project', backref='team', lazy=True)


class Sponsor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    company = db.Column(db.String(120))
    bio = db.Column(db.Text)
    # НОВОЕ: кошелёк инвестора — 10 000 ₽ при регистрации
    balance = db.Column(db.Float, nullable=False, default=10000.0)

    user = db.relationship('User', backref=db.backref('sponsor', uselist=False))
    purchases = db.relationship(
        'Sponsorship', backref='sponsor', lazy=True,
        foreign_keys='Sponsorship.sponsor_id',
    )


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('research_team.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)

    total_shares = db.Column(db.Integer, nullable=False, default=100)
    share_price = db.Column(db.Float, nullable=False, default=1.0)
    sold_shares = db.Column(db.Integer, nullable=False, default=0)

    ip_asset_type = db.Column(db.String(150), default='Патент на изобретение')
    royalty_percentage = db.Column(db.Float, default=20.0)
    monetization_scenario = db.Column(db.Text, default='Продажа лицензий / Роялти с продаж')
    milestone = db.Column(db.String(200), default='Доля фиксируется после подачи заявки на патент')

    score = db.Column(db.Integer, default=5)
    score_explanation = db.Column(db.Text, default='')

    # --- Эскроу ---
    escrow_released = db.Column(db.Float, nullable=False, default=0.0)

    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sponsorships = db.relationship('Sponsorship', backref='project', lazy=True)
    updates = db.relationship(
        'ProjectUpdate', backref='project', lazy=True,
        cascade='all, delete-orphan',
        order_by='ProjectUpdate.created_at.desc()',
    )
    milestones = db.relationship(
        'Milestone', backref='project', lazy=True,
        cascade='all, delete-orphan',
        order_by='Milestone.id',
    )
    holdings = db.relationship('ShareHolding', backref='project', lazy=True)
    listings = db.relationship('ShareListing', backref='project', lazy=True)

    @property
    def ip_valuation(self):
        return round(self.total_shares * self.share_price, 2)

    @property
    def goal(self):
        return round(self.total_shares * self.share_price, 2)

    @property
    def raised(self):
        return round(self.sold_shares * self.share_price, 2)

    @property
    def shares_left(self):
        return max(self.total_shares - self.sold_shares, 0)

    @property
    def progress(self):
        if self.total_shares <= 0:
            return 0
        return min(round(self.sold_shares / self.total_shares * 100), 100)

    @property
    def escrow_balance(self):
        released = self.escrow_released or 0
        return round(max(self.raised - released, 0), 2)

    @property
    def team_received(self):
        return round(self.escrow_released or 0, 2)

    @property
    def milestones_completed(self):
        return sum(1 for m in self.milestones if m.status == 'completed')


class Sponsorship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('sponsor.id'), nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProjectUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- НОВЫЕ МОДЕЛИ ----------

class Milestone(db.Model):
    """Веха финансирования. Средства эскроу освобождаются по мере закрытия вех."""
    __tablename__ = 'milestone'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default='')
    percentage = db.Column(db.Float, nullable=False)       # % от собранной суммы
    status = db.Column(db.String(20), default='pending')   # pending | completed
    released_amount = db.Column(db.Float, default=0.0)     # сколько уже выплачено по вехе
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)


class ShareHolding(db.Model):
    """Текущее владение долями проекта. Источник истины для P2P-сделок."""
    __tablename__ = 'share_holding'

    id = db.Column(db.Integer, primary_key=True)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('sponsor.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    shares = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint('sponsor_id', 'project_id', name='_sponsor_project_uc'),
    )

    sponsor = db.relationship('Sponsor', backref='holdings')


class ShareListing(db.Model):
    """Лот вторичного рынка (P2P)."""
    __tablename__ = 'share_listing'

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('sponsor.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    price_per_share = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='active')   # active | sold | cancelled
    buyer_id = db.Column(db.Integer, db.ForeignKey('sponsor.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sold_at = db.Column(db.DateTime, nullable=True)

    seller = db.relationship('Sponsor', foreign_keys=[seller_id], backref='listings')
    buyer = db.relationship('Sponsor', foreign_keys=[buyer_id])

    @property
    def total_price(self):
        return round(self.shares * self.price_per_share, 2)