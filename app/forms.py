from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, Optional


class LoginForm(FlaskForm):
    email = StringField('Identifiant', validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    submit = SubmitField('Se connecter')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Mot de passe actuel', validators=[DataRequired()])
    new_password = PasswordField('Nouveau mot de passe', validators=[
        DataRequired(),
        Length(min=8, message='Le mot de passe doit contenir au moins 8 caractères.'),
    ])
    confirm_password = PasswordField('Confirmer le nouveau mot de passe', validators=[
        DataRequired(),
        EqualTo('new_password', message='Les mots de passe ne correspondent pas.'),
    ])
    submit = SubmitField('Changer le mot de passe')


class ProfileForm(FlaskForm):
    nom = StringField('Nom', validators=[DataRequired()])
    prenom = StringField('Prénom', validators=[DataRequired()])
    submit = SubmitField('Enregistrer')


# ---------------------------------------------------------------------------
# Référentiel
# ---------------------------------------------------------------------------

class ParcoursForm(FlaskForm):
    nom = StringField('Nom (affichage)', validators=[DataRequired()])
    code = StringField('Code (fichiers)', validators=[DataRequired(), Length(max=20)])
    submit = SubmitField('Enregistrer')


class AnneeAcademiqueForm(FlaskForm):
    libelle = StringField('Libellé (ex: 2024-2025)', validators=[DataRequired()])
    code = StringField('Code (ex: 2024-2025)', validators=[DataRequired(), Length(max=20)])
    submit = SubmitField('Enregistrer')


class ClasseForm(FlaskForm):
    nom = StringField('Nom (affichage)', validators=[DataRequired()])
    code = StringField('Code (ex: PC, SVT)', validators=[DataRequired(), Length(max=20)])
    parcours_id = SelectField('Parcours', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Enregistrer')


class SemestreForm(FlaskForm):
    nom = StringField('Nom (affichage)', validators=[DataRequired()])
    code = StringField('Code (ex: S1, S3)', validators=[DataRequired(), Length(max=10)])
    classe_id = SelectField('Classe', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Enregistrer')


class AffectationForm(FlaskForm):
    utilisateur_id = SelectField('Chef de Parcours', coerce=int, validators=[DataRequired()])
    parcours_id = SelectField('Parcours', coerce=int, validators=[DataRequired()])
    annee_debut_id = SelectField('Année début', coerce=int, validators=[DataRequired()])
    annee_fin_id = SelectField('Année fin (optionnel)', coerce=int, validators=[Optional()])
    submit = SubmitField('Enregistrer')


# ---------------------------------------------------------------------------
# Gestion Utilisateurs
# ---------------------------------------------------------------------------

class CreateUserForm(FlaskForm):
    nom = StringField('Nom', validators=[DataRequired()])
    prenom = StringField('Prénom', validators=[DataRequired()])
    email = StringField('Identifiant (email)', validators=[DataRequired()])
    password = PasswordField('Mot de passe temporaire', validators=[
        DataRequired(),
        Length(min=8, message='Minimum 8 caractères.'),
    ])
    role = SelectField('Rôle', choices=[
        ('chef_parcours', 'Chef de Parcours'),
        ('directeur_etudes', 'Directeur des Études'),
        ('admin', 'Administrateur'),
    ], validators=[DataRequired()])
    submit = SubmitField('Créer le compte')


class CreateChefForm(FlaskForm):
    """Formulaire simplifié pour le Directeur — rôle fixé à chef_parcours."""
    nom = StringField('Nom', validators=[DataRequired()])
    prenom = StringField('Prénom', validators=[DataRequired()])
    email = StringField('Identifiant (email)', validators=[DataRequired()])
    password = PasswordField('Mot de passe temporaire', validators=[
        DataRequired(),
        Length(min=8, message='Minimum 8 caractères.'),
    ])
    submit = SubmitField('Créer le compte')


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField('Nouveau mot de passe', validators=[
        DataRequired(),
        Length(min=8, message='Minimum 8 caractères.'),
    ])
    submit = SubmitField('Réinitialiser')
