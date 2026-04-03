"""Routes de consultation et téléchargement des relevés.

Partagé entre Directeur des Études et Admin.
"""
import io
import os
import zipfile

from flask import (Blueprint, render_template, request, send_file, abort,
                   current_app, flash, redirect, url_for)
from flask_login import login_required, current_user

from app import db
from app.models import (
    Parcours, AnneeAcademique, Classe, Semestre, Releve,
)
from app.utils import role_required, must_change_password, log_audit, delete_file

bp = Blueprint('consultation', __name__, url_prefix='/consultation')


@bp.route('/')
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def index():
    # Filtres
    parcours_id = request.args.get('parcours_id', type=int)
    annee_id = request.args.get('annee_id', type=int)

    parcours_list = Parcours.query.order_by(Parcours.nom).all()
    annees = AnneeAcademique.query.order_by(AnneeAcademique.code).all()

    query = Releve.query
    if parcours_id:
        query = query.filter_by(parcours_id=parcours_id)
    if annee_id:
        query = query.filter_by(annee_academique_id=annee_id)

    releves = query.order_by(Releve.date_depot.desc()).all()

    return render_template('consultation/index.html',
                           releves=releves,
                           parcours_list=parcours_list, annees=annees,
                           parcours_id=parcours_id, annee_id=annee_id)


# ── Télécharger un relevé ────────────────────────────────────────────────

@bp.route('/telecharger/<int:releve_id>')
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def telecharger(releve_id):
    releve = Releve.query.get_or_404(releve_id)
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'],
                             releve.fichier_chemin)
    if not os.path.exists(full_path):
        abort(404)
    return send_file(full_path, as_attachment=True,
                     download_name=releve.nom_fichier_original)


# ── Remplacer (Admin uniquement) ─────────────────────────────────────────

@bp.route('/remplacer/<int:releve_id>', methods=['POST'])
@login_required
@must_change_password
@role_required('admin')
def remplacer(releve_id):
    from app.utils import allowed_file, save_upload

    releve = Releve.query.get_or_404(releve_id)
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Aucun fichier sélectionné.', 'warning')
        return redirect(url_for('consultation.index'))

    if not allowed_file(file.filename):
        flash('Format non autorisé.', 'danger')
        return redirect(url_for('consultation.index'))

    delete_file(releve.fichier_chemin)

    relative_path = save_upload(file, releve.parcours.code,
                                releve.annee_academique.code,
                                releve.classe.code, releve.semestre.code)

    releve.fichier_chemin = relative_path
    releve.nom_fichier_original = file.filename
    releve.taille_fichier = file.content_length or os.path.getsize(
        os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path))
    releve.depose_par_id = current_user.id
    db.session.commit()

    log_audit(current_user.id, 'remplacement_releve_admin',
              f'{releve.parcours.code}/{releve.annee_academique.code}',
              request.remote_addr)
    flash('Relevé remplacé.', 'success')
    return redirect(url_for('consultation.index'))


# ── Supprimer (Admin uniquement) ─────────────────────────────────────────

@bp.route('/supprimer/<int:releve_id>', methods=['POST'])
@login_required
@must_change_password
@role_required('admin')
def supprimer(releve_id):
    releve = Releve.query.get_or_404(releve_id)
    delete_file(releve.fichier_chemin)
    info = f'{releve.parcours.code}/{releve.annee_academique.code}/{releve.classe.code}_{releve.semestre.code}'
    db.session.delete(releve)
    db.session.commit()
    log_audit(current_user.id, 'suppression_releve_admin', info, request.remote_addr)
    flash('Relevé supprimé.', 'success')
    return redirect(url_for('consultation.index'))


# ── Téléchargement ZIP (R25) ─────────────────────────────────────────────

@bp.route('/zip')
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def download_zip():
    parcours_id = request.args.get('parcours_id', type=int)
    annee_id = request.args.get('annee_id', type=int)

    if not parcours_id:
        flash('Veuillez sélectionner un parcours.', 'warning')
        return redirect(url_for('consultation.index'))

    parcours = Parcours.query.get_or_404(parcours_id)

    query = Releve.query.filter_by(parcours_id=parcours_id)
    if annee_id:
        query = query.filter_by(annee_academique_id=annee_id)

    releves = query.all()

    if not releves:
        flash('Aucun relevé trouvé pour cette sélection.', 'warning')
        return redirect(url_for('consultation.index'))

    # Générer le ZIP en mémoire
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for r in releves:
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'],
                                     r.fichier_chemin)
            if os.path.exists(full_path):
                # Structure: AnnéeAcadémique/Classe_Semestre.xlsx
                arc_name = f'{r.annee_academique.code}/{r.classe.code}_{r.semestre.code}.xlsx'
                zf.write(full_path, arc_name)

    buffer.seek(0)

    if annee_id:
        annee = AnneeAcademique.query.get(annee_id)
        zip_name = f'Releves_{parcours.code}_{annee.code}.zip'
    else:
        zip_name = f'Releves_{parcours.code}.zip'

    log_audit(current_user.id, 'telechargement_zip', zip_name, request.remote_addr)

    return send_file(buffer, as_attachment=True, download_name=zip_name,
                     mimetype='application/zip')
