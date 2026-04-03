from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app import db, limiter
from app.forms import LoginForm, ChangePasswordForm, ProfileForm
from app.models import User
from app.utils import log_audit, must_change_password

bp = Blueprint('auth', __name__)


@bp.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if current_user.doit_changer_mdp:
        return redirect(url_for('auth.change_password'))
    # Redirection vers le dashboard du rôle
    role_blueprint = {
        'admin': 'admin',
        'directeur_etudes': 'directeur',
        'chef_parcours': 'chef_parcours',
    }
    bp_name = role_blueprint.get(current_user.role, 'auth')
    return redirect(url_for(f'{bp_name}.dashboard'))


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('5 per minute')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.actif and user.check_password(form.password.data):
            login_user(user)
            log_audit(user.id, 'connexion', ip=request.remote_addr)
            flash('Connexion réussie.', 'success')
            return redirect(url_for('auth.index'))
        flash('Identifiant ou mot de passe incorrect.', 'danger')

    return render_template('auth/login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    log_audit(current_user.id, 'deconnexion', ip=request.remote_addr)
    logout_user()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/changer-mot-de-passe', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Mot de passe actuel incorrect.', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            current_user.doit_changer_mdp = False
            db.session.commit()
            log_audit(current_user.id, 'changement_mdp', ip=request.remote_addr)
            flash('Mot de passe modifié avec succès.', 'success')
            return redirect(url_for('auth.index'))

    return render_template('auth/change_password.html', form=form,
                           forced=current_user.doit_changer_mdp)


@bp.route('/profil', methods=['GET', 'POST'])
@login_required
@must_change_password
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.nom = form.nom.data
        current_user.prenom = form.prenom.data
        db.session.commit()
        log_audit(current_user.id, 'modification_profil', ip=request.remote_addr)
        flash('Profil mis à jour.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html', form=form)
