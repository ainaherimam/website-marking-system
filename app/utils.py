import os
from functools import wraps

from flask import abort, current_app, flash, redirect, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename

from app import db
from app.models import AuditLog


def role_required(*roles):
    """Décorateur pour restreindre l'accès à certains rôles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def must_change_password(f):
    """Redirige vers le changement de mdp si doit_changer_mdp est True."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.doit_changer_mdp:
            flash('Vous devez changer votre mot de passe avant de continuer.', 'warning')
            return redirect(url_for('auth.change_password'))
        return f(*args, **kwargs)
    return decorated_function


def log_audit(user_id, action, details=None, ip=None):
    """Enregistre une entrée dans le journal d'audit."""
    entry = AuditLog(
        utilisateur_id=user_id,
        action=action,
        details=details,
        adresse_ip=ip,
    )
    db.session.add(entry)
    db.session.commit()


# ---------------------------------------------------------------------------
# File upload helpers
# ---------------------------------------------------------------------------

def allowed_file(filename):
    """Vérifie que l'extension est autorisée (.xlsx, .xls)."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in current_app.config['ALLOWED_EXTENSIONS']


def build_storage_path(parcours_code, annee_code, classe_code, semestre_code):
    """Construit le chemin de stockage basé sur les codes (R24).

    Returns (directory, filename) — ex: ('PHY/2024-2025', 'PC_S3.xlsx')
    """
    directory = os.path.join(parcours_code, annee_code)
    filename = f'{classe_code}_{semestre_code}.xlsx'
    return directory, filename


def save_upload(file, parcours_code, annee_code, classe_code, semestre_code):
    """Sauvegarde un fichier uploadé et retourne le chemin relatif."""
    directory, stored_name = build_storage_path(
        parcours_code, annee_code, classe_code, semestre_code)
    full_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], directory)
    os.makedirs(full_dir, exist_ok=True)
    full_path = os.path.join(full_dir, stored_name)
    file.save(full_path)
    return os.path.join(directory, stored_name)


def delete_file(relative_path):
    """Supprime un fichier stocké."""
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)
