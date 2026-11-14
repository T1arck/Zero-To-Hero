from flask_wtf import FlaskForm
from wtforms import (
    FloatField, IntegerField, PasswordField, SelectField,
    StringField, SubmitField, TextAreaField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange


class RegisterForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[
        DataRequired(message='Это поле обязательно для заполнения'),
        Length(min=3, max=30, message='Имя должно быть от 3 до 30 символов'),
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Введите ваш email'),
        Email(message='Введите корректный адрес электронной почты'),
    ])
    role = SelectField('Тип аккаунта', choices=[
        ('sponsor', 'Инвестор'),
        ('team', 'Разработчик / научная команда'),
    ])
    password = PasswordField('Пароль', validators=[
        DataRequired(message='Придумайте пароль'),
        Length(min=6, message='Пароль должен содержать минимум 6 символов'),
    ])
    password2 = PasswordField('Повторите пароль', validators=[
        DataRequired(message='Повторите пароль'),
        EqualTo('password', message='Пароли не совпадают'),
    ])
    submit = SubmitField('Зарегистрироваться')


class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(message='Введите имя пользователя')])
    password = PasswordField('Пароль', validators=[DataRequired(message='Введите пароль')])
    submit = SubmitField('Войти')


class ProjectForm(FlaskForm):
    title = StringField('Название проекта', validators=[
        DataRequired(message='Придумайте название'),
        Length(min=3, max=150, message='Название должно быть от 3 до 150 символов'),
    ])
    description = TextAreaField('Описание проекта', validators=[
        DataRequired(message='Добавьте описание проекта'),
        Length(min=20, message='Описание должно содержать минимум 20 символов'),
    ])
    total_shares = IntegerField('Всего долей', validators=[
        DataRequired(message='Укажите количество долей'),
        NumberRange(min=1, max=1_000_000, message='Количество долей должно быть от 1 до 1 000 000'),
    ])
    share_price = FloatField('Цена одной доли (₽)', validators=[
        DataRequired(message='Укажите цену доли'),
        NumberRange(min=0.01, message='Цена должна быть больше 0'),
    ])
    ip_asset_type = StringField('Тип актива ИС', validators=[
        DataRequired(message='Укажите тип актива (например, Патент)'),
        Length(max=150, message='Максимум 150 символов'),
    ])
    royalty_percentage = FloatField('Процент роялти (%)', validators=[
        DataRequired(message='Укажите процент роялти'),
        NumberRange(min=0, max=100, message='Процент должен быть от 0 до 100'),
    ])
    monetization_scenario = TextAreaField('Сценарий монетизации', validators=[
        DataRequired(message='Опишите сценарий монетизации'),
    ])
    submit = SubmitField('Опубликовать проект')


class BuySharesForm(FlaskForm):
    amount = FloatField('Сумма инвестиций (₽)', validators=[
        DataRequired(message='Введите сумму инвестиций'),
        NumberRange(min=1, message='Минимальная сумма инвестиций — 1 ₽'),
    ])
    submit = SubmitField('Купить долю в ИС')


class ProjectUpdateForm(FlaskForm):
    title = StringField('Заголовок отчёта', validators=[
        DataRequired(message='Придумайте заголовок'),
        Length(min=3, max=150, message='Заголовок должен быть от 3 до 150 символов'),
    ])
    content = TextAreaField('Текст отчёта', validators=[DataRequired(message='Заполните текст отчета')])
    submit = SubmitField('Опубликовать отчёт')


# ---------- НОВЫЕ ФОРМЫ ----------

class MilestoneForm(FlaskForm):
    title = StringField('Название вехи', validators=[
        DataRequired(message='Укажите название'),
        Length(min=3, max=150, message='От 3 до 150 символов'),
    ])
    description = TextAreaField('Описание', validators=[])
    percentage = FloatField('Доля финансирования (%)', validators=[
        DataRequired(message='Укажите процент'),
        NumberRange(min=0.01, max=100, message='От 0.01 до 100'),
    ])
    submit = SubmitField('Добавить веху')


class ListSharesForm(FlaskForm):
    shares = IntegerField('Количество долей', validators=[
        DataRequired(message='Укажите количество'),
        NumberRange(min=1, message='Минимум 1 доля'),
    ])
    price_per_share = FloatField('Цена за долю (₽)', validators=[
        DataRequired(message='Укажите цену'),
        NumberRange(min=0.01, message='Цена должна быть больше 0'),
    ])
    submit = SubmitField('Выставить на продажу')