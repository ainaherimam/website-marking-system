import os

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, current_app, send_file, abort)
from flask_login import login_required, current_user

from app import db, limiter
from app.models import (
    Parcours, AnneeAcademique, Classe, Semestre, Affectation, Releve,
)
from app.utils import (
    role_required, must_change_password, log_audit,
    allowed_file, save_upload, delete_file,
)

bp = Blueprint('chef_parcours', __name__, template_folder='../templates/chef')


def _get_chef_parcours_ids():
    """Retourne les IDs de parcours auxquels le chef est affecté (actif)."""
    affectations = Affectation.query.filter_by(
        utilisateur_id=current_user.id
    ).all()
    return [a.parcours_id for a in affectations]


def _get_chef_context():
    """Retourne parcours et années disponibles pour ce chef."""
    parcours_ids = _get_chef_parcours_ids()
    parcours_list = Parcours.query.filter(Parcours.id.in_(parcours_ids)).order_by(Parcours.nom).all()

    annees = AnneeAcademique.query.order_by(AnneeAcademique.code).all()
    return parcours_list, annees


# ── Dashboard (R26) ─────────────────────────────────────────────────────

@bp.route('/dashboard')
@login_required
@must_change_password
@role_required('chef_parcours')
def dashboard():
    parcours_list, annees = _get_chef_context()

    # Calcul synthèse par parcours/année
    synthese = []
    for p in parcours_list:
        for a in annees:
            classes = Classe.query.filter_by(parcours_id=p.id).all()
            total_attendu = 0
            total_depose = 0
            manquants = []

            for c in classes:
                semestres = Semestre.query.filter_by(classe_id=c.id).all()
                for s in semestres:
                    total_attendu += 1
                    releve = Releve.query.filter_by(
                        parcours_id=p.id, annee_academique_id=a.id,
                        classe_id=c.id, semestre_id=s.id
                    ).first()
                    if releve:
                        total_depose += 1
                    else:
                        manquants.append(f'{c.nom} — {s.nom}')

            if total_attendu > 0:
                synthese.append({
                    'parcours': p,
                    'annee': a,
                    'total': total_attendu,
                    'deposes': total_depose,
                    'pct': round(total_depose / total_attendu * 100),
                    'manquants': manquants,
                })

    return render_template('chef/dashboard.html', synthese=synthese)


# ── Page Dépôt ───────────────────────────────────────────────────────────

@bp.route('/depot')
@bp.route('/depot/<int:parcours_id>/<int:annee_id>')
@login_required
@must_change_password
@role_required('chef_parcours')
def depot(parcours_id=None, annee_id=None):
    parcours_list, annees = _get_chef_context()
    parcours_ids = [p.id for p in parcours_list]

    selected_parcours = None
    selected_annee = None
    grille = []

    if parcours_id and annee_id:
        if parcours_id not in parcours_ids:
            abort(403)
        selected_parcours = Parcours.query.get_or_404(parcours_id)
        selected_annee = AnneeAcademique.query.get_or_404(annee_id)

        classes = Classe.query.filter_by(parcours_id=parcours_id).order_by(Classe.code).all()
        for c in classes:
            semestres = Semestre.query.filter_by(classe_id=c.id).order_by(Semestre.code).all()
            for s in semestres:
                releve = Releve.query.filter_by(
                    parcours_id=parcours_id, annee_academique_id=annee_id,
                    classe_id=c.id, semestre_id=s.id
                ).first()
                grille.append({
                    'classe': c,
                    'semestre': s,
                    'releve': releve,
                })

    return render_template('chef/depot.html',
                           parcours_list=parcours_list, annees=annees,
                           selected_parcours=selected_parcours,
                           selected_annee=selected_annee,
                           grille=grille)


# ── Upload ───────────────────────────────────────────────────────────────

@bp.route('/upload/<int:parcours_id>/<int:annee_id>/<int:classe_id>/<int:semestre_id>',
          methods=['POST'])
@login_required
@must_change_password
@role_required('chef_parcours')
@limiter.limit('10 per minute')
def upload(parcours_id, annee_id, classe_id, semestre_id):
    # Vérifier que le chef a accès à ce parcours
    if parcours_id not in _get_chef_parcours_ids():
        abort(403)

    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Aucun fichier sélectionné.', 'warning')
        return redirect(url_for('chef_parcours.depot',
                                parcours_id=parcours_id, annee_id=annee_id))

    if not allowed_file(file.filename):
        flash('Format non autorisé. Seuls .xlsx et .xls sont acceptés.', 'danger')
        return redirect(url_for('chef_parcours.depot',
                                parcours_id=parcours_id, annee_id=annee_id))

    # Vérifier qu'il n'existe pas déjà un relevé
    existing = Releve.query.filter_by(
        parcours_id=parcours_id, annee_academique_id=annee_id,
        classe_id=classe_id, semestre_id=semestre_id
    ).first()
    if existing:
        flash('Un relevé existe déjà pour cet emplacement. Utilisez Remplacer.', 'warning')
        return redirect(url_for('chef_parcours.depot',
                                parcours_id=parcours_id, annee_id=annee_id))

    parcours = Parcours.query.get_or_404(parcours_id)
    annee = AnneeAcademique.query.get_or_404(annee_id)
    classe = Classe.query.get_or_404(classe_id)
    semestre = Semestre.query.get_or_404(semestre_id)

    relative_path = save_upload(file, parcours.code, annee.code,
                                classe.code, semestre.code)

    releve = Releve(
        classe_id=classe_id,
        semestre_id=semestre_id,
        annee_academique_id=annee_id,
        parcours_id=parcours_id,
        fichier_chemin=relative_path,
        nom_fichier_original=file.filename,
        taille_fichier=file.content_length or os.path.getsize(
            os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path)),
        depose_par_id=current_user.id,
    )
    db.session.add(releve)
    db.session.commit()

    log_audit(current_user.id, 'depot_releve',
              f'{parcours.code}/{annee.code}/{classe.code}_{semestre.code}',
              request.remote_addr)
    flash(f'Relevé déposé pour {classe.nom} — {semestre.nom}.', 'success')
    return redirect(url_for('chef_parcours.depot',
                            parcours_id=parcours_id, annee_id=annee_id))


# ── Remplacer ────────────────────────────────────────────────────────────

@bp.route('/remplacer/<int:releve_id>', methods=['POST'])
@login_required
@must_change_password
@role_required('chef_parcours')
@limiter.limit('10 per minute')
def remplacer(releve_id):
    releve = Releve.query.get_or_404(releve_id)
    if releve.parcours_id not in _get_chef_parcours_ids():
        abort(403)

    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Aucun fichier sélectionné.', 'warning')
        return redirect(url_for('chef_parcours.depot',
                                parcours_id=releve.parcours_id,
                                annee_id=releve.annee_academique_id))

    if not allowed_file(file.filename):
        flash('Format non autorisé. Seuls .xlsx et .xls sont acceptés.', 'danger')
        return redirect(url_for('chef_parcours.depot',
                                parcours_id=releve.parcours_id,
                                annee_id=releve.annee_academique_id))

    # Supprimer l'ancien fichier
    delete_file(releve.fichier_chemin)

    # Sauvegarder le nouveau
    parcours = releve.parcours
    annee = releve.annee_academique
    classe = releve.classe
    semestre = releve.semestre

    relative_path = save_upload(file, parcours.code, annee.code,
                                classe.code, semestre.code)

    releve.fichier_chemin = relative_path
    releve.nom_fichier_original = file.filename
    releve.taille_fichier = file.content_length or os.path.getsize(
        os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path))
    releve.depose_par_id = current_user.id
    db.session.commit()

    log_audit(current_user.id, 'remplacement_releve',
              f'{parcours.code}/{annee.code}/{classe.code}_{semestre.code}',
              request.remote_addr)
    flash(f'Relevé remplacé pour {classe.nom} — {semestre.nom}.', 'success')
    return redirect(url_for('chef_parcours.depot',
                            parcours_id=releve.parcours_id,
                            annee_id=releve.annee_academique_id))


# ── Supprimer ────────────────────────────────────────────────────────────

@bp.route('/supprimer/<int:releve_id>', methods=['POST'])
@login_required
@must_change_password
@role_required('chef_parcours')
def supprimer(releve_id):
    releve = Releve.query.get_or_404(releve_id)
    if releve.parcours_id not in _get_chef_parcours_ids():
        abort(403)

    delete_file(releve.fichier_chemin)
    info = f'{releve.parcours.code}/{releve.annee_academique.code}/{releve.classe.code}_{releve.semestre.code}'
    parcours_id = releve.parcours_id
    annee_id = releve.annee_academique_id

    db.session.delete(releve)
    db.session.commit()

    log_audit(current_user.id, 'suppression_releve', info, request.remote_addr)
    flash('Relevé supprimé.', 'success')
    return redirect(url_for('chef_parcours.depot',
                            parcours_id=parcours_id, annee_id=annee_id))


# ── Télécharger ──────────────────────────────────────────────────────────

@bp.route('/telecharger/<int:releve_id>')
@login_required
@must_change_password
@role_required('chef_parcours')
def telecharger(releve_id):
    releve = Releve.query.get_or_404(releve_id)
    if releve.parcours_id not in _get_chef_parcours_ids():
        abort(403)

    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'],
                             releve.fichier_chemin)
    if not os.path.exists(full_path):
        abort(404)

    return send_file(full_path, as_attachment=True,
                     download_name=releve.nom_fichier_original)
