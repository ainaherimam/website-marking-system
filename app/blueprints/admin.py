import csv
import io
import os
import shutil

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_required, current_user

from app import db
from app.models import (User, AuditLog, ParametreSysteme, Parcours,
                        AnneeAcademique, Classe, Semestre, Affectation, Releve)
from app.forms import CreateUserForm, ResetPasswordForm, ResetSystemForm, CSVImportForm
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
        'releves': Releve.query.count(),
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


# ── Paramètres Système ───────────────────────────────────────────────────

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


# ── Réinitialisation du Système (Roadmap 12.1) ──────────────────────────

@bp.route('/reinitialiser', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('admin')
def reinitialiser():
    form = ResetSystemForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.password.data):
            flash('Mot de passe incorrect.', 'danger')
            return render_template('admin/reinitialiser.html', form=form)

        # Delete all data in correct order (foreign keys)
        Releve.query.delete()
        Affectation.query.delete()
        AuditLog.query.delete()
        Semestre.query.delete()
        Classe.query.delete()
        Parcours.query.delete()
        AnneeAcademique.query.delete()
        ParametreSysteme.query.delete()
        User.query.delete()

        # Delete uploaded files
        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if upload_folder and os.path.exists(upload_folder):
            shutil.rmtree(upload_folder)
            os.makedirs(upload_folder, exist_ok=True)

        # Recreate default accounts
        admin = User(
            nom='Administrateur', prenom='Système', email='admin',
            role='admin', actif=True, doit_changer_mdp=True,
        )
        admin.set_password('admin')
        db.session.add(admin)

        directeur = User(
            nom='Directeur', prenom='Des Études', email='directeur',
            role='directeur_etudes', actif=True, doit_changer_mdp=True,
        )
        directeur.set_password('1234')
        db.session.add(directeur)

        # Recreate default parameters
        db.session.add(ParametreSysteme(cle='taille_max_fichier_mo', valeur='10'))
        db.session.add(ParametreSysteme(cle='timeout_session_minutes', valeur='30'))

        db.session.commit()

        # Log out and redirect to login
        from flask_login import logout_user
        logout_user()
        flash('Le système a été réinitialisé. Connectez-vous avec les identifiants par défaut.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('admin/reinitialiser.html', form=form)


# ── Import CSV en masse (Roadmap 12.2) ──────────────────────────────────

CSV_TYPES = {
    'annees': {
        'label': 'Années académiques',
        'columns': ['libelle', 'code'],
        'example': 'libelle,code\n2024-2025,2024-2025',
    },
    'parcours': {
        'label': 'Parcours',
        'columns': ['nom', 'code'],
        'example': 'nom,code\nPhysique,PHY',
    },
    'classes': {
        'label': 'Classes',
        'columns': ['nom', 'code', 'code_parcours'],
        'example': 'nom,code,code_parcours\nPhysique-Chimie,PC,PHY',
    },
    'semestres': {
        'label': 'Semestres',
        'columns': ['nom', 'code', 'code_classe'],
        'example': 'nom,code,code_classe\nSemestre 1,S1,PC',
    },
    'utilisateurs': {
        'label': 'Utilisateurs',
        'columns': ['nom', 'prenom', 'email', 'role', 'mot_de_passe'],
        'example': 'nom,prenom,email,role,mot_de_passe\nDupont,Jean,jdupont,chef_parcours,motdepasse1',
    },
}


@bp.route('/import-csv', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('admin')
def import_csv():
    form = CSVImportForm()
    csv_type = request.args.get('type', 'annees')
    if csv_type not in CSV_TYPES:
        csv_type = 'annees'
    type_info = CSV_TYPES[csv_type]

    preview = None
    errors = []

    # Handle confirm action (data stored in session from preview step)
    if request.method == 'POST' and request.form.get('action') == 'confirm':
        cached = session.pop(f'csv_import_{csv_type}', None)
        if cached:
            try:
                count = _import_csv_rows(csv_type, cached)
                log_audit(current_user.id, 'import_csv',
                          f'{type_info["label"]}: {count} lignes importées',
                          request.remote_addr)
                flash(f'{count} enregistrement(s) importé(s) avec succès.', 'success')
            except Exception as e:
                flash(f'Erreur lors de l\'import : {e}', 'danger')
        else:
            flash('Session expirée. Veuillez re-télécharger le fichier.', 'warning')
        return redirect(url_for('admin.import_csv', type=csv_type))

    if form.validate_on_submit():
        file = form.csv_file.data
        try:
            content = file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content))

            # Validate columns
            if reader.fieldnames:
                missing = set(type_info['columns']) - set(reader.fieldnames)
                if missing:
                    flash(f'Colonnes manquantes : {", ".join(missing)}', 'danger')
                    return render_template('admin/import_csv.html', form=form,
                                           csv_type=csv_type, csv_types=CSV_TYPES,
                                           preview=None, errors=[])

            rows = list(reader)
            if not rows:
                flash('Le fichier CSV est vide.', 'warning')
                return render_template('admin/import_csv.html', form=form,
                                       csv_type=csv_type, csv_types=CSV_TYPES,
                                       preview=None, errors=[])

            # Validate each row
            preview, errors = _validate_csv_rows(csv_type, rows, type_info)

            # Store validated rows in session for the confirm step
            if not errors:
                session[f'csv_import_{csv_type}'] = rows

        except UnicodeDecodeError:
            flash('Erreur de décodage. Assurez-vous que le fichier est encodé en UTF-8.', 'danger')
        except csv.Error as e:
            flash(f'Erreur de lecture CSV : {e}', 'danger')

    return render_template('admin/import_csv.html', form=form,
                           csv_type=csv_type, csv_types=CSV_TYPES,
                           preview=preview, errors=errors)


def _validate_csv_rows(csv_type, rows, type_info):
    """Validate CSV rows and return (preview_rows, errors)."""
    preview = []
    errors = []

    for i, row in enumerate(rows, start=2):
        line_errors = []
        vals = {col: (row.get(col) or '').strip() for col in type_info['columns']}

        # Check required fields
        for col in type_info['columns']:
            if not vals[col]:
                line_errors.append(f'Colonne « {col} » vide')

        if not line_errors:
            if csv_type == 'annees':
                if AnneeAcademique.query.filter_by(code=vals['code']).first():
                    line_errors.append(f'Code « {vals["code"]} » déjà existant')

            elif csv_type == 'parcours':
                if Parcours.query.filter_by(code=vals['code']).first():
                    line_errors.append(f'Code « {vals["code"]} » déjà existant')

            elif csv_type == 'classes':
                p = Parcours.query.filter_by(code=vals['code_parcours']).first()
                if not p:
                    line_errors.append(f'Parcours « {vals["code_parcours"]} » introuvable')
                elif Classe.query.filter_by(code=vals['code'], parcours_id=p.id).first():
                    line_errors.append(f'Classe « {vals["code"]} » déjà existante pour ce parcours')

            elif csv_type == 'semestres':
                c = Classe.query.filter_by(code=vals['code_classe']).first()
                if not c:
                    line_errors.append(f'Classe « {vals["code_classe"]} » introuvable')
                elif Semestre.query.filter_by(code=vals['code'], classe_id=c.id).first():
                    line_errors.append(f'Semestre « {vals["code"]} » déjà existant pour cette classe')

            elif csv_type == 'utilisateurs':
                if User.query.filter_by(email=vals['email']).first():
                    line_errors.append(f'Identifiant « {vals["email"]} » déjà utilisé')
                if vals.get('role') not in ('chef_parcours', 'directeur_etudes', 'admin'):
                    line_errors.append(f'Rôle « {vals.get("role")} » invalide')
                if vals.get('role') == 'directeur_etudes' and \
                        User.query.filter_by(role='directeur_etudes').first():
                    line_errors.append('Un Directeur des Études existe déjà (R13)')
                if len(vals.get('mot_de_passe', '')) < 8:
                    line_errors.append('Mot de passe trop court (min 8 caractères)')

        if line_errors:
            errors.append((i, line_errors))

        preview.append(vals)

    return preview, errors


def _import_csv_rows(csv_type, rows):
    """Import validated CSV rows. Returns count of imported rows."""
    count = 0
    for row in rows:
        vals = {col: (row.get(col) or '').strip() for col in CSV_TYPES[csv_type]['columns']}

        if csv_type == 'annees':
            db.session.add(AnneeAcademique(libelle=vals['libelle'], code=vals['code']))

        elif csv_type == 'parcours':
            db.session.add(Parcours(nom=vals['nom'], code=vals['code']))

        elif csv_type == 'classes':
            p = Parcours.query.filter_by(code=vals['code_parcours']).first()
            db.session.add(Classe(nom=vals['nom'], code=vals['code'], parcours_id=p.id))

        elif csv_type == 'semestres':
            c = Classe.query.filter_by(code=vals['code_classe']).first()
            db.session.add(Semestre(nom=vals['nom'], code=vals['code'], classe_id=c.id))

        elif csv_type == 'utilisateurs':
            user = User(
                nom=vals['nom'], prenom=vals['prenom'], email=vals['email'],
                role=vals['role'], actif=True, doit_changer_mdp=True,
            )
            user.set_password(vals['mot_de_passe'])
            db.session.add(user)

        count += 1

    db.session.commit()
    return count
