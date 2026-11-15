import os
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask, abort, flash, redirect, render_template, request, url_for,
)
from flask_login import (
    LoginManager, current_user, login_required, login_user, logout_user,
)
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from models import (
    db, User, Sponsor, ResearchTeam, Project, Sponsorship, ProjectUpdate,
    Milestone, ShareHolding, ShareListing,
)
from forms import (
    RegisterForm, LoginForm, ProjectForm, BuySharesForm, ProjectUpdateForm,
    MilestoneForm, ListSharesForm,
)


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'

db.init_app(app)
csrf = CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ---------- Вспомогательные функции ----------

def get_or_create_holding(sponsor_id, project_id):
    holding = ShareHolding.query.filter_by(
        sponsor_id=sponsor_id, project_id=project_id
    ).first()
    if holding:
        return holding
    holding = ShareHolding(
        sponsor_id=sponsor_id, project_id=project_id, shares=0,
    )
    db.session.add(holding)
    return holding


def sync_milestone_funds(project):
    """Освобождает средства эскроу по завершённым вехам (с учётом роста raised)."""
    for m in project.milestones:
        if m.status != 'completed':
            continue
        target = (m.percentage / 100.0) * project.raised
        delta = target - (m.released_amount or 0)
        if delta <= 0:
            continue
        available = project.escrow_balance
        release = min(delta, available)
        if release > 0:
            m.released_amount = (m.released_amount or 0) + release
            project.escrow_released = (project.escrow_released or 0) + release


# ---------- Публичные страницы ----------

@app.route('/')
def index():
    projects = (
        Project.query
        .filter_by(status='active')
        .order_by(Project.created_at.desc())
        .all()
    )
    return render_template('index.html', projects=projects)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('account'))

    form = RegisterForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()

        if User.query.filter_by(username=username).first():
            flash('Имя уже занято', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email уже зарегистрирован', 'danger')
            return redirect(url_for('register'))

        user = User(
            username=username,
            email=email,
            role=form.role.data,
        )
        user.set_password(form.password.data)

        try:
            db.session.add(user)
            db.session.flush()

            if user.role == 'sponsor':
                # НОВОЕ: стартовый баланс 10 000 ₽
                db.session.add(Sponsor(
                    user_id=user.id, company='', bio='', balance=10000.0,
                ))
            elif user.role == 'team':
                db.session.add(ResearchTeam(
                    user_id=user.id, name='', description='', field='',
                ))
            else:
                db.session.rollback()
                abort(400)

            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(
                'Пользователь с таким именем или email уже существует',
                'danger',
            )
            return redirect(url_for('register'))

        login_user(user, remember=True)
        flash('Аккаунт создан. Вы вошли в систему.', 'success')
        return redirect(url_for('account'))

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('account'))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(
            username=form.username.data.strip()
        ).first()

        if user and user.check_password(form.password.data):
            login_user(user, remember=True)

            next_url = request.args.get('next')
            if next_url and urlparse(next_url).netloc == '':
                return redirect(next_url)

            return redirect(url_for('account'))

        flash('Неверные учётные данные', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из аккаунта', 'info')
    return redirect(url_for('index'))


@app.route('/account')
@login_required
def account():
    if current_user.role == 'team':
        team = ResearchTeam.query.filter_by(
            user_id=current_user.id
        ).first_or_404()

        projects = (
            Project.query
            .filter_by(team_id=team.id)
            .order_by(Project.created_at.desc())
            .all()
        )

        return render_template(
            'team_dashboard.html',
            team=team,
            projects=projects,
        )

    if current_user.role == 'sponsor':
        sponsor = Sponsor.query.filter_by(
            user_id=current_user.id
        ).first_or_404()

        projects = (
            Project.query
            .filter_by(status='active')
            .order_by(Project.created_at.desc())
            .all()
        )

        purchases = (
            Sponsorship.query
            .filter_by(sponsor_id=sponsor.id)
            .order_by(Sponsorship.created_at.desc())
            .all()
        )

        return render_template(
            'sponsor_dashboard.html',
            sponsor=sponsor,
            projects=projects,
            donations=purchases,
            form=BuySharesForm(),
        )

    abort(403)


@app.route('/team/profile', methods=['GET', 'POST'])
@role_required('team')
def team_profile():
    team = ResearchTeam.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    if request.method == 'POST':
        team.name = request.form.get('name', '').strip()
        team.description = request.form.get('description', '').strip()
        team.field = request.form.get('field', '').strip()
        db.session.commit()
        flash('Профиль обновлён', 'success')
        return redirect(url_for('account'))

    return render_template('team_profile.html', team=team)


@app.route('/sponsor/profile', methods=['GET', 'POST'])
@role_required('sponsor')
def sponsor_profile():
    sponsor = Sponsor.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    if request.method == 'POST':
        sponsor.company = request.form.get('company', '').strip()
        sponsor.bio = request.form.get('bio', '').strip()
        db.session.commit()
        flash('Профиль обновлён', 'success')
        return redirect(url_for('account'))

    return render_template('sponsor_profile.html', sponsor=sponsor)


# ---------- Проекты ----------

@app.route('/team/project/new', methods=['GET', 'POST'])
@role_required('team')
def create_project():
    team = ResearchTeam.query.filter_by(
        user_id=current_user.id
    ).first_or_404()
    form = ProjectForm()

    if form.validate_on_submit():
        project = Project(
            team_id=team.id,
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            total_shares=form.total_shares.data,
            share_price=form.share_price.data,
            ip_asset_type=form.ip_asset_type.data.strip(),
            royalty_percentage=form.royalty_percentage.data,
            monetization_scenario=form.monetization_scenario.data.strip(),
            sold_shares=0,
            status='active',
        )
        db.session.add(project)
        db.session.commit()

        flash(
            'Проект опубликован. Настройте вехи финансирования для '
            'получения средств из эскроу.',
            'success',
        )
        return redirect(url_for('project_funds', project_id=project.id))

    return render_template('create_project.html', form=form)


@app.route('/project/<int:project_id>/update/new', methods=['GET', 'POST'])
@role_required('team')
def create_project_update(project_id):
    project = Project.query.get_or_404(project_id)

    if project.team.user_id != current_user.id:
        abort(403)

    form = ProjectUpdateForm()

    if form.validate_on_submit():
        update = ProjectUpdate(
            project_id=project.id,
            title=form.title.data.strip(),
            content=form.content.data.strip(),
        )
        db.session.add(update)
        db.session.commit()
        flash('Отчёт опубликован!', 'success')
        return redirect(url_for('project_detail', project_id=project.id))

    return render_template('update.html', form=form, project=project)


@app.route('/projects')
def projects_page():
    projects = (
        Project.query
        .filter_by(status='active')
        .order_by(Project.created_at.desc())
        .all()
    )
    return render_template('projects.html', projects=projects)


app.add_url_rule(
    '/projects',
    endpoint='projects_catalog',
    view_func=projects_page,
)


@app.route('/projects/<int:project_id>')
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)

    sponsors = (
        db.session.query(
            Sponsor,
            db.func.sum(Sponsorship.shares).label('total_shares'),
            db.func.sum(Sponsorship.amount).label('total_amount'),
        )
        .join(Sponsorship, Sponsorship.sponsor_id == Sponsor.id)
        .filter(Sponsorship.project_id == project.id)
        .group_by(Sponsor.id)
        .order_by(db.func.sum(Sponsorship.amount).desc())
        .all()
    )

    active_listings = (
        ShareListing.query
        .filter_by(project_id=project.id, status='active')
        .order_by(ShareListing.price_per_share.asc())
        .all()
    )

    return render_template(
        'project_detail.html',
        project=project,
        sponsors=sponsors,
        form=BuySharesForm(),
        active_listings=active_listings,
    )


@app.route('/projects/<int:project_id>/buy', methods=['POST'])
@role_required('sponsor')
def buy_shares(project_id):
    project = Project.query.get_or_404(project_id)
    form = BuySharesForm()

    if not form.validate_on_submit():
        flash('Укажите корректную сумму инвестиций.', 'danger')
        return redirect(url_for('project_detail', project_id=project.id))

    if project.status != 'active':
        flash('Проект больше не продаёт доли.', 'warning')
        return redirect(url_for('project_detail', project_id=project.id))

    amount = form.amount.data
    shares = int(amount / project.share_price)

    if shares < 1:
        flash('Сумма слишком мала для покупки хотя бы одной доли.', 'warning')
        return redirect(url_for('project_detail', project_id=project.id))

    if shares > project.shares_left:
        flash(
            f'Осталось всего {project.shares_left} долей. '
            'Укажите меньшую сумму.',
            'warning',
        )
        return redirect(url_for('project_detail', project_id=project.id))

    actual_amount = round(shares * project.share_price, 2)
    sponsor = Sponsor.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    # НОВОЕ: проверка баланса кошелька
    if (sponsor.balance or 0) < actual_amount:
        flash(
            f'Недостаточно средств. На кошельке: '
            f'{sponsor.balance:.2f} ₽, требуется: {actual_amount:.2f} ₽.',
            'danger',
        )
        return redirect(url_for('project_detail', project_id=project.id))

    # НОВОЕ: списываем средства
    sponsor.balance = round((sponsor.balance or 0) - actual_amount, 2)

    project.sold_shares += shares
    if project.sold_shares >= project.total_shares:
        project.sold_shares = project.total_shares
        project.status = 'funded'

    db.session.add(Sponsorship(
        project_id=project.id,
        sponsor_id=sponsor.id,
        shares=shares,
        amount=actual_amount,
    ))

    holding = get_or_create_holding(sponsor.id, project.id)
    holding.shares += shares

    sync_milestone_funds(project)
    db.session.commit()

    flash(
        f'Куплено {shares} долей на {actual_amount:.2f} ₽. '
        f'Остаток на кошельке: {sponsor.balance:.2f} ₽. '
        'Средства зарезервированы в эскроу и будут перечислены команде '
        'по мере закрытия вех.',
        'success',
    )
    return redirect(url_for('project_detail', project_id=project.id))


@app.route('/my-projects')
@login_required
def my_projects():
    if current_user.role == 'team':
        team = ResearchTeam.query.filter_by(
            user_id=current_user.id
        ).first_or_404()
        projects = (
            Project.query
            .filter_by(team_id=team.id)
            .order_by(Project.created_at.desc())
            .all()
        )
    elif current_user.role == 'sponsor':
        sponsor = Sponsor.query.filter_by(
            user_id=current_user.id
        ).first_or_404()
        projects = (
            Project.query
            .join(Sponsorship)
            .filter(Sponsorship.sponsor_id == sponsor.id)
            .distinct()
            .order_by(Project.created_at.desc())
            .all()
        )
    else:
        abort(403)

    return render_template('my_projects.html', projects=projects)


@app.route('/team/<int:team_id>')
def team_public(team_id):
    team = ResearchTeam.query.get_or_404(team_id)
    return render_template('team_profile.html', team=team, public=True)


@app.route('/sponsor/<int:sponsor_id>')
def sponsor_public(sponsor_id):
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    return render_template('sponsor_profile.html', sponsor=sponsor, public=True)


# =============================================================
#  MILESTONE-BASED ESCROW
# =============================================================

@app.route('/project/<int:project_id>/funds')
@login_required
def project_funds(project_id):
    project = Project.query.get_or_404(project_id)

    if current_user.role == 'team' and project.team.user_id != current_user.id:
        abort(403)

    total_pct = sum(m.percentage for m in project.milestones)

    return render_template(
        'project_funds.html',
        project=project,
        total_pct=total_pct,
        form=MilestoneForm(),
    )


@app.route('/project/<int:project_id>/milestones/new', methods=['POST'])
@role_required('team')
def add_milestone(project_id):
    project = Project.query.get_or_404(project_id)

    if project.team.user_id != current_user.id:
        abort(403)

    form = MilestoneForm()

    if not form.validate_on_submit():
        flash('Проверьте данные вехи.', 'danger')
        return redirect(url_for('project_funds', project_id=project.id))

    current_total = sum(m.percentage for m in project.milestones)

    if current_total + form.percentage.data > 100.0001:
        flash(
            f'Сумма процентов всех вех не может превышать 100% '
            f'(сейчас: {current_total:.1f}%).',
            'danger',
        )
        return redirect(url_for('project_funds', project_id=project.id))

    db.session.add(Milestone(
        project_id=project.id,
        title=form.title.data.strip(),
        description=(form.description.data or '').strip(),
        percentage=form.percentage.data,
    ))
    db.session.commit()

    flash('Веха добавлена.', 'success')
    return redirect(url_for('project_funds', project_id=project.id))


@app.route('/milestone/<int:milestone_id>/complete', methods=['POST'])
@role_required('team')
def complete_milestone(milestone_id):
    m = Milestone.query.get_or_404(milestone_id)

    if m.project.team.user_id != current_user.id:
        abort(403)

    if m.status == 'completed':
        flash('Веха уже завершена.', 'info')
        return redirect(url_for('project_funds', project_id=m.project_id))

    m.status = 'completed'
    m.completed_at = datetime.utcnow()

    old_released = m.project.escrow_released or 0
    sync_milestone_funds(m.project)
    released_now = (m.project.escrow_released or 0) - old_released
    db.session.commit()

    flash(
        f'Веха «{m.title}» закрыта. '
        f'Освобождено {released_now:.2f} ₽ из эскроу.',
        'success',
    )
    return redirect(url_for('project_funds', project_id=m.project_id))


# =============================================================
#  P2P-РЫНОК ДОЛЕЙ
# =============================================================

@app.route('/market')
@login_required
def market():
    listings = (
        ShareListing.query
        .filter_by(status='active')
        .order_by(ShareListing.created_at.desc())
        .all()
    )
    return render_template('market.html', listings=listings)


@app.route('/my-shares')
@role_required('sponsor')
def my_shares():
    sponsor = Sponsor.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    holdings = (
        ShareHolding.query
        .filter_by(sponsor_id=sponsor.id)
        .filter(ShareHolding.shares > 0)
        .all()
    )

    active_listings = (
        ShareListing.query
        .filter_by(seller_id=sponsor.id, status='active')
        .order_by(ShareListing.created_at.desc())
        .all()
    )

    return render_template(
        'my_shares.html',
        sponsor=sponsor,
        holdings=holdings,
        listings=active_listings,
    )


@app.route('/market/list/<int:project_id>', methods=['GET', 'POST'])
@role_required('sponsor')
def list_shares(project_id):
    project = Project.query.get_or_404(project_id)
    sponsor = Sponsor.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    holding = ShareHolding.query.filter_by(
        sponsor_id=sponsor.id, project_id=project.id,
    ).first()

    if not holding or holding.shares <= 0:
        flash('У вас нет свободных долей этого проекта.', 'danger')
        return redirect(url_for('my_shares'))

    form = ListSharesForm()

    if form.validate_on_submit():
        shares = form.shares.data

        if shares > holding.shares:
            flash(
                f'У вас только {holding.shares} свободных долей.',
                'danger',
            )
            return render_template(
                'list_shares.html',
                form=form, project=project, holding=holding,
            )

        holding.shares -= shares
        db.session.add(ShareListing(
            seller_id=sponsor.id,
            project_id=project.id,
            shares=shares,
            price_per_share=form.price_per_share.data,
            status='active',
        ))
        db.session.commit()

        flash(f'Лот на {shares} долей выставлен на рынок.', 'success')
        return redirect(url_for('my_shares'))

    return render_template(
        'list_shares.html', form=form, project=project, holding=holding,
    )


@app.route('/market/<int:listing_id>/cancel', methods=['POST'])
@role_required('sponsor')
def cancel_listing(listing_id):
    listing = ShareListing.query.get_or_404(listing_id)
    sponsor = Sponsor.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    if listing.seller_id != sponsor.id:
        abort(403)

    if listing.status != 'active':
        flash('Лот уже неактивен.', 'info')
        return redirect(url_for('my_shares'))

    listing.status = 'cancelled'
    holding = get_or_create_holding(sponsor.id, listing.project_id)
    holding.shares += listing.shares
    db.session.commit()

    flash('Продажа отменена, доли возвращены в портфель.', 'info')
    return redirect(url_for('my_shares'))


@app.route('/market/<int:listing_id>/buy', methods=['POST'])
@role_required('sponsor')
def buy_listing(listing_id):
    listing = ShareListing.query.get_or_404(listing_id)
    buyer = Sponsor.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    if listing.status != 'active':
        flash('Лот уже неактивен.', 'warning')
        return redirect(url_for('market'))

    if listing.seller_id == buyer.id:
        flash('Нельзя купить собственный лот.', 'warning')
        return redirect(url_for('market'))

    total_price = listing.total_price

    # НОВОЕ: проверка баланса покупателя
    if (buyer.balance or 0) < total_price:
        flash(
            f'Недостаточно средств. На кошельке: '
            f'{buyer.balance:.2f} ₽, требуется: {total_price:.2f} ₽.',
            'danger',
        )
        return redirect(url_for('market'))

    # НОВОЕ: списываем у покупателя, начисляем продавцу
    buyer.balance = round((buyer.balance or 0) - total_price, 2)
    seller = db.session.get(Sponsor, listing.seller_id)
    if seller:
        seller.balance = round((seller.balance or 0) + total_price, 2)

    listing.status = 'sold'
    listing.buyer_id = buyer.id
    listing.sold_at = datetime.utcnow()

    buyer_holding = get_or_create_holding(buyer.id, listing.project_id)
    buyer_holding.shares += listing.shares

    db.session.commit()

    flash(
        f'Куплено {listing.shares} долей за {total_price:.2f} ₽ '
        f'(вторичный рынок). Остаток на кошельке: {buyer.balance:.2f} ₽.',
        'success',
    )
    return redirect(url_for('my_shares'))


# =============================================================
#  СХЕМА БД: идемпотентная миграция при старте
# =============================================================

def _ensure_schema():
    """Догоняет схему БД до текущих моделей. Безопасно вызывать многократно."""
    inspector = inspect(db.engine)
    pre_tables = set(inspector.get_table_names())

    # 1) Добавляем недостающие колонки в существующие таблицы
    if 'project' in pre_tables:
        cols = {c['name'] for c in inspector.get_columns('project')}
        if 'escrow_released' not in cols:
            with db.engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE project "
                    "ADD COLUMN escrow_released FLOAT NOT NULL DEFAULT 0.0"
                ))
            print('[migrate] project.escrow_released — добавлена')

    # НОВОЕ: кошелёк спонсора
    if 'sponsor' in pre_tables:
        cols = {c['name'] for c in inspector.get_columns('sponsor')}
        if 'balance' not in cols:
            with db.engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE sponsor "
                    "ADD COLUMN balance FLOAT NOT NULL DEFAULT 10000.0"
                ))
            print('[migrate] sponsor.balance — добавлена (10 000 ₽ каждому)')

    # 2) Создаём недостающие таблицы (milestone, share_holding, share_listing)
    db.create_all()

    # 3) Бэкфилл ShareHolding из существующих Sponsorship —
    #    только в момент, когда share_holding появляется впервые.
    if 'share_holding' not in pre_tables:
        agg = (
            db.session.query(
                Sponsorship.sponsor_id,
                Sponsorship.project_id,
                db.func.sum(Sponsorship.shares).label('total'),
            )
            .group_by(Sponsorship.sponsor_id, Sponsorship.project_id)
            .all()
        )
        for sponsor_id, project_id, total in agg:
            db.session.add(ShareHolding(
                sponsor_id=sponsor_id,
                project_id=project_id,
                shares=int(total or 0),
            ))
        if agg:
            db.session.commit()
            print(f'[migrate] ShareHolding — бэкфилл {len(agg)} записей')


with app.app_context():
    _ensure_schema()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)