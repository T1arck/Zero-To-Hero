from flask_wtf import FlaskForm
from wtforms import (
    FloatField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
)


class RegisterForm(FlaskForm):
    username = StringField(
        'Имя пользователя',
        validators=[DataRequired(), Length(min=3, max=30)],
    )
    email = StringField(
        'Email',
        validators=[DataRequired(), Email()],
    )
    role = SelectField(
        'Тип аккаунта',
        choices=[
            ('sponsor', 'Инвестор'),
            ('team', 'Разработчик / научная команда'),
        ],
    )
    password = PasswordField(
        'Пароль',
        validators=[DataRequired(), Length(min=6)],
    )
    password2 = PasswordField(
        'Повторите пароль',
        validators=[DataRequired(), EqualTo('password')],
    )
    submit = SubmitField('Зарегистрироваться')


class LoginForm(FlaskForm):
    username = StringField(
        'Имя пользователя',
        validators=[DataRequired()],
    )
    password = PasswordField(
        'Пароль',
        validators=[DataRequired()],
    )
    submit = SubmitField('Войти')


class SponsorshipRequestForm(FlaskForm):
    title = StringField(
        'Заголовок заявки',
        validators=[DataRequired(), Length(min=3, max=150)],
    )
    description = TextAreaField(
        'Описание задачи/тематики',
        validators=[DataRequired()],
    )
    budget = FloatField(
        'Бюджет (руб.)',
        validators=[DataRequired(), NumberRange(min=1)],
    )
    submit = SubmitField('Опубликовать заявку')


class ProjectForm(FlaskForm):
    title = StringField(
        'Название проекта',
        validators=[DataRequired(), Length(min=3, max=150)],
    )
    description = TextAreaField(
        'Описание проекта',
        validators=[DataRequired(), Length(min=20)],
    )
    goal = FloatField(
        'Цель сбора (₽)',
        validators=[DataRequired(), NumberRange(min=1)],
    )
    submit = SubmitField('Опубликовать проект')


class DonationForm(FlaskForm):
    amount = FloatField(
        'Сумма пожертвования (₽)',
        validators=[DataRequired(), NumberRange(min=1)],
    )
    submit = SubmitField('Поддержать проект')


class ResponseForm(FlaskForm):
    pitch = TextAreaField(
        'Ваше предложение',
        validators=[DataRequired()],
    )
    submit = SubmitField('Откликнуться')