import os
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Sponsor, ResearchTeam, Project, SponsorshipRequest, Response, Sponsorship
from forms import RegisterForm, LoginForm, SponsorshipRequestForm, ResponseForm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-me-in-prod'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def role_required(role):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.route('/')
def index():
    projects = Project.query.filter_by(status='active').order_by(Project.created_at.desc()).all()
    requests = SponsorshipRequest.query.filter_by(status='open').order_by(SponsorshipRequest.created_at.desc()).all()
    return render_template('index.html', projects=projects, requests=requests)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Имя уже занято', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=form.email.data).first():
            flash('Email уже зарегистрирован', 'danger')
            return redirect(url_for('register'))

        user = User(username=form.username.data, email=form.email.data, role=form.role.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        if user.role == 'sponsor':
            db.session.add(Sponsor(user_id=user.id, company='', bio=''))
        else:
            db.session.add(ResearchTeam(user_id=user.id, name='', description='', field=''))
        db.session.commit()

        flash('Регистрация успешна. Войдите в аккаунт.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_url = request.args.get('next')
            return redirect(next_url or url_for('index'))
        flash('Неверные учётные данные', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/sponsor/profile', methods=['GET', 'POST'])
@role_required('sponsor')
def sponsor_profile():
    sponsor = Sponsor.query.filter_by(user_id=current_user.id).first()
    if request.method == 'POST':
        sponsor.company = request.form.get('company', '')
        sponsor.bio = request.form.get('bio', '')
        db.session.commit()
        flash('Профиль обновлён', 'success')
        return redirect(url_for('sponsor_profile'))
    return render_template('sponsor_profile.html', sponsor=sponsor)


@app.route('/sponsor/request/new', methods=['GET', 'POST'])
@role_required('sponsor')
def create_request():
    form = SponsorshipRequestForm()
    if form.validate_on_submit():
        sponsor = Sponsor.query.filter_by(user_id=current_user.id).first()
        req = SponsorshipRequest(
            sponsor_id=sponsor.id,
            title=form.title.data,
            description=form.description.data,
            budget=form.budget.data,
        )
        db.session.add(req)
        db.session.commit()
        flash('Заявка опубликована', 'success')
        return redirect(url_for('sponsor_profile'))
    return render_template('create_request.html', form=form)


@app.route('/sponsor/request/<int:req_id>')
def request_detail(req_id):
    req = SponsorshipRequest.query.get_or_404(req_id)
    return render_template('request_detail.html', req=req)


@app.route('/sponsor/response/<int:resp_id>/<action>', methods=['POST'])
@role_required('sponsor')
def handle_response(resp_id, action):
    if action not in ('accept', 'reject'):
        abort(400)
    resp = Response.query.get_or_404(resp_id)
    req = resp.request
    if req.sponsor.user_id != current_user.id:
        abort(403)

    if action == 'accept':
        resp.status = 'accepted'
        req.status = 'taken'
        project = Project(
            team_id=resp.team_id,
            title=req.title,
            description=req.description,
            goal=req.budget,
            raised=req.budget,
            status='funded',
        )
        db.session.add(project)
        db.session.flush()
        db.session.add(Sponsorship(project_id=project.id, sponsor_id=req.sponsor_id, amount=req.budget))
        flash('Отклик принят. Проект создан и профинансирован.', 'success')
    else:
        resp.status = 'rejected'
        flash('Отклик отклонён', 'info')
    db.session.commit()
    return redirect(url_for('sponsor_profile'))


# ---------- Научная команда ----------
@app.route('/team/profile', methods=['GET', 'POST'])
@role_required('team')
def team_profile():
    team = ResearchTeam.query.filter_by(user_id=current_user.id).first()
    if request.method == 'POST':
        team.name = request.form.get('name', '')
        team.description = request.form.get('description', '')
        team.field = request.form.get('field', '')
        db.session.commit()
        flash('Профиль обновлён', 'success')
        return redirect(url_for('team_profile'))
    return render_template('team_profile.html', team=team)


@app.route('/team/respond/<int:req_id>', methods=['GET', 'POST'])
@role_required('team')
def respond_to_request(req_id):
    req = SponsorshipRequest.query.get_or_404(req_id)
    if req.status != 'open':
        flash('Заявка уже закрыта', 'warning')
        return redirect(url_for('index'))
    team = ResearchTeam.query.filter_by(user_id=current_user.id).first()
    existing = Response.query.filter_by(request_id=req.id, team_id=team.id).first()
    if existing:
        flash('Вы уже откликнулись на эту заявку', 'info')
        return redirect(url_for('team_profile'))

    form = ResponseForm()
    if form.validate_on_submit():
        resp = Response(request_id=req.id, team_id=team.id, pitch=form.pitch.data)
        db.session.add(resp)
        db.session.commit()
        flash('Отклик отправлен', 'success')
        return redirect(url_for('team_profile'))
    return render_template('respond.html', req=req, form=form)


@app.route('/team/<int:team_id>')
def team_public(team_id):
    team = ResearchTeam.query.get_or_404(team_id)
    return render_template('team_profile.html', team=team, public=True)


@app.route('/sponsor/<int:sponsor_id>')
def sponsor_public(sponsor_id):
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    return render_template('sponsor_profile.html', sponsor=sponsor, public=True)


with app.app_context():
    db.create_all()

@app.route('/analytics')
def analytics():
    total_projects = Project.query.count()
    total_sponsors = Sponsor.query.count()
    total_sum = db.session.query(db.func.coalesce(db.func.sum(Sponsorship.amount), 0)).scalar()
    
    # Проекты по категориям (по полю field команды)
    categories = db.session.query(
        ResearchTeam.field, db.func.count(Project.id)
    ).join(Project).group_by(ResearchTeam.field).all()
    
    # Топ спонсоров
    top_sponsors = db.session.query(
        Sponsor, db.func.sum(Sponsorship.amount).label('total')
    ).join(Sponsorship).group_by(Sponsor.id).order_by(db.text('total DESC')).limit(3).all()
    
    return render_template('analytics.html',
        total_projects=total_projects,
        total_sponsors=total_sponsors,
        total_sum=total_sum,
        categories=categories,
        top_sponsors=top_sponsors
    )

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)