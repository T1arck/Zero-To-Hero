from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, TextAreaField, FloatField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, EqualTo


class RegisterForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(3, 30)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Роль', choices=[('sponsor', 'Спонсор'), ('team', 'Научная команда')])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(6)])
    password2 = PasswordField('Повторите пароль', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')


class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')


class SponsorshipRequestForm(FlaskForm):
    title = StringField('Заголовок заявки', validators=[DataRequired(), Length(3, 150)])
    description = TextAreaField('Описание задачи/тематики', validators=[DataRequired()])
    budget = FloatField('Бюджет (руб.)', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Опубликовать заявку')


class ResponseForm(FlaskForm):
    pitch = TextAreaField('Ваше предложение (что и как будете делать)', validators=[DataRequired()])
    submit = SubmitField('Откликнуться')