from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models import User, AuditLog, ParametreSysteme
from app.forms import CreateUserForm, ResetPasswordForm
from app.utils import role_required, must_change_password, log_audit

bp = Blueprint('admin', __name__, template_folder='../templates/admin')


@bp.route('/dashboard')
@login_required
@must_change_password
@role_required('admin')
def dashboard():
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(actif=True).count(),
        'chefs': User.query.filter_by(role='chef_parcours', actif=True).count(),
    }
    return render_template('admin/dashboard.html', stats=stats)


# ── Gestion Utilisateurs ─────────────────────────────────��──────────────

@bp.route('/utilisateurs')
@login_required
@must_change_password
@role_required('admin')
def utilisateurs():
    users = User.query.order_by(User.role, User.nom).all()
    return render_template('admin/utilisateurs.html', users=users)


@bp.route('/utilisateurs/ajouter', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('admin')
def user_add():
    form = CreateUserForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Cet identifiant est déjà utilisé.', 'danger')
        elif form.role.data == 'directeur_etudes' and \
                User.query.filter_by(role='directeur_etudes').first():
            flash('Un Directeur des Études existe déjà (R13).', 'danger')
        else:
            user = User(
                nom=form.nom.data,
                prenom=form.prenom.data,
                email=form.email.data,
                role=form.role.data,
                actif=True,
                doit_changer_mdp=True,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            log_audit(current_user.id, 'creation_utilisateur',
                      f'{user.role}: {user.prenom} {user.nom} ({user.email})',
                      request.remote_addr)
            flash(f'Compte créé pour {user.prenom} {user.nom}.', 'success')
            return redirect(url_for('admin.utilisateurs'))
    return render_template('admin/user_form.html', form=form, title='Créer un utilisateur')


@bp.route('/utilisateurs/<int:id>/toggle', methods=['POST'])
@login_required
@must_change_password
@role_required('admin')
def user_toggle(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Vous ne pouvez pas vous désactiver vous-même.', 'danger')
    else:
        user.actif = not user.actif
        db.session.commit()
        action = 'activation' if user.actif else 'desactivation'
        log_audit(current_user.id, f'{action}_utilisateur',
                  f'{user.prenom} {user.nom} ({user.email})', request.remote_addr)
        etat = 'activé' if user.actif else 'désactivé'
        flash(f'{user.prenom} {user.nom} a été {etat}.', 'success')
    return redirect(url_for('admin.utilisateurs'))


@bp.route('/utilisateurs/<int:id>/reset-mdp', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('admin')
def user_reset_password(id):
    user = User.query.get_or_404(id)
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        user.doit_changer_mdp = True
        db.session.commit()
        log_audit(current_user.id, 'reset_mdp',
                  f'MDP réinitialisé pour {user.prenom} {user.nom}',
                  request.remote_addr)
        flash(f'Mot de passe réinitialisé pour {user.prenom} {user.nom}.', 'success')
        return redirect(url_for('admin.utilisateurs'))
    return render_template('admin/user_form.html', form=form,
                           title=f'Réinitialiser le MDP de {user.prenom} {user.nom}')


# ── Redirections vers blueprints partagés ────────────────────────────────

@bp.route('/referentiel')
@login_required
@must_change_password
@role_required('admin')
def referentiel():
    return redirect(url_for('referentiel.index'))


@bp.route('/consultation')
@login_required
@must_change_password
@role_required('admin')
def consultation():
    return redirect(url_for('consultation.index'))


# ── Journal d'Audit ──────────────────────────────────────────────────────

@bp.route('/audit')
@login_required
@must_change_password
@role_required('admin')
def audit():
    page = request.args.get('page', 1, type=int)
    query = AuditLog.query.order_by(AuditLog.date_heure.desc())

    # Filtres
    user_filter = request.args.get('user_id', type=int)
    action_filter = request.args.get('action', '')
    if user_filter:
        query = query.filter_by(utilisateur_id=user_filter)
    if action_filter:
        query = query.filter(AuditLog.action.ilike(f'%{action_filter}%'))

    pagination = query.paginate(page=page, per_page=50, error_out=False)
    users = User.query.order_by(User.nom).all()
    return render_template('admin/audit.html', logs=pagination.items,
                           pagination=pagination, users=users,
                           user_filter=user_filter, action_filter=action_filter)


# ── Paramètres Système ──────────────────────────────────��────────────────

@bp.route('/parametres', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('admin')
def parametres():
    params = {p.cle: p for p in ParametreSysteme.query.all()}
    if request.method == 'POST':
        for cle, param in params.items():
            new_val = request.form.get(cle, param.valeur)
            if new_val != param.valeur:
                param.valeur = new_val
        db.session.commit()
        log_audit(current_user.id, 'modification_parametres', ip=request.remote_addr)
        flash('Paramètres mis à jour.', 'success')
        return redirect(url_for('admin.parametres'))
    return render_template('admin/parametres.html', params=params)
