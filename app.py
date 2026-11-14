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
from sqlalchemy.exc import IntegrityError

from models import (
    db, User, Sponsor, ResearchTeam, Project,
    SponsorshipRequest, Response, Sponsorship,
)
from forms import (
    RegisterForm, LoginForm, SponsorshipRequestForm,
    ResponseForm, ProjectForm, DonationForm,
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
    requests = (
        SponsorshipRequest.query
        .filter_by(status='open')
        .order_by(SponsorshipRequest.created_at.desc())
        .all()
    )
    return render_template(
        'index.html',
        projects=projects,
        requests=requests,
    )


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

        donations = (
            Sponsorship.query
            .filter_by(sponsor_id=sponsor.id)
            .order_by(Sponsorship.created_at.desc())
            .all()
        )

        return render_template(
            'sponsor_dashboard.html',
            sponsor=sponsor,
            projects=projects,
            donations=donations,
            form=DonationForm(),
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
            goal=form.goal.data,
            raised=0,
            status='active',
        )
        db.session.add(project)
        db.session.commit()

        flash('Проект опубликован и сохранён.', 'success')
        return redirect(url_for('account'))

    return render_template('create_project.html', form=form)


@app.route('/projects', endpoint='projects')
def projects_page():
    projects = (
        Project.query
        .filter_by(status='active')
        .order_by(Project.created_at.desc())
        .all()
    )
    return render_template('projects.html', projects=projects)


# Старое имя endpoint тоже поддерживается шаблонами.
app.add_url_rule(
    '/projects',
    endpoint='projects_catalog',
    view_func=projects_page,
)


@app.route('/projects/<int:project_id>')
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)

    goal = project.goal or 0
    raised = project.raised or 0
    progress = min(round(raised / goal * 100), 100) if goal > 0 else 0

    # Складываем все взносы одного спонсора в одну строку.
    sponsors = (
        db.session.query(
            Sponsor,
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
        progress=progress,
        sponsors=sponsors,
        form=DonationForm(),
    )


@app.route('/projects/<int:project_id>/donate', methods=['POST'])
@role_required('sponsor')
def donate(project_id):
    project = Project.query.get_or_404(project_id)
    form = DonationForm()

    if not form.validate_on_submit():
        flash('Укажите корректную сумму пожертвования.', 'danger')
        return redirect(
            url_for('project_detail', project_id=project.id)
        )

    if project.status != 'active':
        flash('Проект больше не принимает пожертвования.', 'warning')
        return redirect(
            url_for('project_detail', project_id=project.id)
        )

    amount = round(float(form.amount.data), 2)
    remaining = max(
        0,
        round(project.goal - (project.raised or 0), 2),
    )

    if amount > remaining:
        flash(
            f'До цели осталось {remaining:.2f} ₽. '
            'Укажите сумму не больше остатка.',
            'warning',
        )
        return redirect(
            url_for('project_detail', project_id=project.id)
        )

    sponsor = Sponsor.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    project.raised = round((project.raised or 0) + amount, 2)

    if project.raised >= project.goal:
        project.raised = project.goal
        project.status = 'funded'

    db.session.add(
        Sponsorship(
            project_id=project.id,
            sponsor_id=sponsor.id,
            amount=amount,
        )
    )
    db.session.commit()

    flash('Пожертвование записано. Спасибо за поддержку!', 'success')
    return redirect(
        url_for('project_detail', project_id=project.id)
    )


@app.route('/sponsor/request/new', methods=['GET', 'POST'])
@role_required('sponsor')
def create_request():
    form = SponsorshipRequestForm()

    if form.validate_on_submit():
        sponsor = Sponsor.query.filter_by(
            user_id=current_user.id
        ).first_or_404()

        new_request = SponsorshipRequest(
            sponsor_id=sponsor.id,
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            budget=form.budget.data,
        )
        db.session.add(new_request)
        db.session.commit()

        flash('Заявка опубликована', 'success')
        return redirect(url_for('account'))

    return render_template('create_request.html', form=form)


@app.route('/sponsor/request/<int:req_id>')
def request_detail(req_id):
    sponsorship_request = SponsorshipRequest.query.get_or_404(req_id)
    return render_template(
        'request_detail.html',
        req=sponsorship_request,
    )


@app.route(
    '/sponsor/response/<int:resp_id>/<action>',
    methods=['POST'],
)
@role_required('sponsor')
def handle_response(resp_id, action):
    if action not in ('accept', 'reject'):
        abort(400)

    response = Response.query.get_or_404(resp_id)
    sponsorship_request = response.request

    if sponsorship_request.sponsor.user_id != current_user.id:
        abort(403)

    if action == 'accept':
        if (
            sponsorship_request.status != 'open'
            or response.status != 'pending'
        ):
            flash('Заявка или отклик уже обработаны', 'warning')
            return redirect(url_for('account'))

        response.status = 'accepted'
        sponsorship_request.status = 'taken'

        project = Project(
            team_id=response.team_id,
            title=sponsorship_request.title,
            description=sponsorship_request.description,
            goal=sponsorship_request.budget,
            raised=sponsorship_request.budget,
            status='funded',
        )
        db.session.add(project)
        db.session.flush()

        db.session.add(
            Sponsorship(
                project_id=project.id,
                sponsor_id=sponsorship_request.sponsor_id,
                amount=sponsorship_request.budget,
            )
        )
        flash('Отклик принят. Проект создан и профинансирован.', 'success')
    else:
        response.status = 'rejected'
        flash('Отклик отклонён', 'info')

    db.session.commit()
    return redirect(url_for('account'))


@app.route('/team/respond/<int:req_id>', methods=['GET', 'POST'])
@role_required('team')
def respond_to_request(req_id):
    sponsorship_request = SponsorshipRequest.query.get_or_404(req_id)

    if sponsorship_request.status != 'open':
        flash('Заявка уже закрыта', 'warning')
        return redirect(url_for('index'))

    team = ResearchTeam.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    existing = Response.query.filter_by(
        request_id=sponsorship_request.id,
        team_id=team.id,
    ).first()

    if existing:
        flash('Вы уже откликнулись на эту заявку', 'info')
        return redirect(url_for('account'))

    form = ResponseForm()

    if form.validate_on_submit():
        db.session.add(
            Response(
                request_id=sponsorship_request.id,
                team_id=team.id,
                pitch=form.pitch.data,
            )
        )
        db.session.commit()
        flash('Отклик отправлен', 'success')
        return redirect(url_for('account'))

    return render_template(
        'respond.html',
        req=sponsorship_request,
        form=form,
    )


@app.route('/my-projects')
@login_required
def my_projects():
    if current_user.role == 'team':
        team = ResearchTeam.query.filter_by(
            user_id=current_user.id
        ).first_or_404()
        projects = Project.query.filter_by(team_id=team.id).all()
    elif current_user.role == 'sponsor':
        sponsor = Sponsor.query.filter_by(
            user_id=current_user.id
        ).first_or_404()
        projects = (
            Project.query
            .join(Sponsorship)
            .filter(Sponsorship.sponsor_id == sponsor.id)
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