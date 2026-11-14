import os
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask, abort, flash, redirect, render_template, request, url_for
)
from flask_login import (
    LoginManager, current_user, login_required, login_user, logout_user
)
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError

from models import (
    db, User, Sponsor, ResearchTeam, Project, Sponsorship, ProjectUpdate,
)
from forms import (
    RegisterForm, LoginForm, ProjectForm, BuySharesForm, ProjectUpdateForm,
)


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY', 'dev-only-change-this'
)
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
                db.session.add(
                    Sponsor(user_id=user.id, company='', bio='')
                )
            elif user.role == 'team':
                db.session.add(
                    ResearchTeam(
                        user_id=user.id,
                        name='',
                        description='',
                        field='',
                    )
                )
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
            sold_shares=0,
            status='active',
        )
        db.session.add(project)
        db.session.commit()

        flash('Проект опубликован. Акции доступны инвесторам.', 'success')
        return redirect(url_for('account'))

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

    return render_template(
        'update.html', # <--- ИСПРАВЛЕНО ЗДЕСЬ
        form=form,
        project=project,
    )


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

    return render_template(
        'project_detail.html',
        project=project,
        sponsors=sponsors,
        form=BuySharesForm(),
    )


@app.route('/projects/<int:project_id>/buy', methods=['POST'])
@role_required('sponsor')
def buy_shares(project_id):
    project = Project.query.get_or_404(project_id)
    form = BuySharesForm()

    if not form.validate_on_submit():
        flash('Укажите корректное количество акций.', 'danger')
        return redirect(
            url_for('project_detail', project_id=project.id)
        )

    if project.status != 'active':
        flash('Проект больше не продаёт акции.', 'warning')
        return redirect(
            url_for('project_detail', project_id=project.id)
        )

    shares = int(form.shares.data)

    if shares > project.shares_left:
        flash(
            f'Осталось всего {project.shares_left} акций. '
            'Укажите меньшее количество.',
            'warning',
        )
        return redirect(
            url_for('project_detail', project_id=project.id)
        )

    amount = round(shares * project.share_price, 2)
    sponsor = Sponsor.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    project.sold_shares += shares
    if project.sold_shares >= project.total_shares:
        project.sold_shares = project.total_shares
        project.status = 'funded'

    db.session.add(
        Sponsorship(
            project_id=project.id,
            sponsor_id=sponsor.id,
            shares=shares,
            amount=amount,
        )
    )
    db.session.commit()

    flash(
        f'Куплено {shares} акций на {amount:.2f} ₽. Спасибо за инвестицию!',
        'success',
    )
    return redirect(
        url_for('project_detail', project_id=project.id)
    )


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
    return render_template(
        'team_profile.html',
        team=team,
        public=True,
    )


@app.route('/sponsor/<int:sponsor_id>')
def sponsor_public(sponsor_id):
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    return render_template(
        'sponsor_profile.html',
        sponsor=sponsor,
        public=True,
    )


with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)