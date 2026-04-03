from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from app import db
from app.models import User
from app.forms import CreateChefForm
from app.utils import role_required, must_change_password, log_audit

bp = Blueprint('directeur', __name__, template_folder='../templates/directeur')


@bp.route('/dashboard')
@login_required
@must_change_password
@role_required('directeur_etudes')
def dashboard():
    return render_template('directeur/dashboard.html')


@bp.route('/consultation')
@login_required
@must_change_password
@role_required('directeur_etudes')
def consultation():
    return redirect(url_for('consultation.index'))


@bp.route('/referentiel')
@login_required
@must_change_password
@role_required('directeur_etudes')
def referentiel():
    return redirect(url_for('referentiel.index'))


@bp.route('/chefs-parcours', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('directeur_etudes')
def gestion_chefs():
    chefs = User.query.filter_by(role='chef_parcours').order_by(User.nom).all()
    form = CreateChefForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Cet identifiant est déjà utilisé.', 'danger')
        else:
            user = User(
                nom=form.nom.data,
                prenom=form.prenom.data,
                email=form.email.data,
                role='chef_parcours',
                actif=True,
                doit_changer_mdp=True,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            log_audit(current_user.id, 'creation_chef',
                      f'Chef {user.prenom} {user.nom} ({user.email}) créé',
                      request.remote_addr)
            flash(f'Compte créé pour {user.prenom} {user.nom}.', 'success')
            return redirect(url_for('directeur.gestion_chefs'))
    return render_template('directeur/gestion_chefs.html', chefs=chefs, form=form)
