"""Routes CRUD pour le référentiel académique.

Partagé entre Directeur des Études et Admin via un blueprint commun.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models import (
    Parcours, AnneeAcademique, Classe, Semestre, Affectation, User, Releve,
)
from app.forms import (
    ParcoursForm, AnneeAcademiqueForm, ClasseForm, SemestreForm, AffectationForm,
)
from app.utils import role_required, must_change_password, log_audit

bp = Blueprint('referentiel', __name__, url_prefix='/referentiel')


# ── Helpers ──────────────────────────────────────────────────────────────

def _back_url():
    return request.args.get('next') or url_for('referentiel.index')


# ── Index ────────────────────────────────────────────────────────────────

@bp.route('/')
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def index():
    tab = request.args.get('tab', 'parcours')
    parcours = Parcours.query.order_by(Parcours.code).all()
    annees = AnneeAcademique.query.order_by(AnneeAcademique.code).all()
    classes = Classe.query.order_by(Classe.parcours_id, Classe.code).all()
    semestres = Semestre.query.order_by(Semestre.classe_id, Semestre.code).all()
    affectations = Affectation.query.all()
    return render_template('referentiel/index.html',
                           tab=tab, parcours=parcours, annees=annees,
                           classes=classes, semestres=semestres,
                           affectations=affectations)


# ── Parcours ─────────────────────────────────────────────────────────────

@bp.route('/parcours/ajouter', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def parcours_add():
    form = ParcoursForm()
    if form.validate_on_submit():
        if Parcours.query.filter_by(code=form.code.data).first():
            flash('Ce code de parcours existe déjà.', 'danger')
        else:
            p = Parcours(nom=form.nom.data, code=form.code.data.upper())
            db.session.add(p)
            db.session.commit()
            log_audit(current_user.id, 'creation_parcours',
                      f'Parcours {p.code} créé', request.remote_addr)
            flash(f'Parcours « {p.nom} » créé.', 'success')
            return redirect(url_for('referentiel.index', tab='parcours'))
    return render_template('referentiel/form.html', form=form,
                           title='Ajouter un parcours')


@bp.route('/parcours/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def parcours_edit(id):
    p = Parcours.query.get_or_404(id)
    form = ParcoursForm(obj=p)
    if form.validate_on_submit():
        dup = Parcours.query.filter(Parcours.code == form.code.data.upper(),
                                     Parcours.id != id).first()
        if dup:
            flash('Ce code est déjà utilisé par un autre parcours.', 'danger')
        else:
            old_code = p.code
            p.nom = form.nom.data
            p.code = form.code.data.upper()
            db.session.commit()
            log_audit(current_user.id, 'modification_parcours',
                      f'Parcours {old_code} → {p.code}', request.remote_addr)
            flash(f'Parcours « {p.nom} » mis à jour.', 'success')
            return redirect(url_for('referentiel.index', tab='parcours'))
    return render_template('referentiel/form.html', form=form,
                           title=f'Modifier parcours « {p.nom} »')


@bp.route('/parcours/<int:id>/supprimer', methods=['POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def parcours_delete(id):
    p = Parcours.query.get_or_404(id)
    # Bloquer si dépendances (R12)
    if p.classes.count() > 0 or Releve.query.filter_by(parcours_id=id).count() > 0:
        flash(f'Impossible de supprimer « {p.nom} » : des classes ou relevés y sont rattachés.', 'danger')
    else:
        # Supprimer les affectations liées aussi
        Affectation.query.filter_by(parcours_id=id).delete()
        db.session.delete(p)
        db.session.commit()
        log_audit(current_user.id, 'suppression_parcours',
                  f'Parcours {p.code} supprimé', request.remote_addr)
        flash(f'Parcours « {p.nom} » supprimé.', 'success')
    return redirect(url_for('referentiel.index', tab='parcours'))


# ── Années Académiques ───────────────────────────────────────────────────

@bp.route('/annees/ajouter', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def annee_add():
    form = AnneeAcademiqueForm()
    if form.validate_on_submit():
        if AnneeAcademique.query.filter_by(code=form.code.data).first():
            flash('Ce code d\'année existe déjà.', 'danger')
        else:
            a = AnneeAcademique(libelle=form.libelle.data, code=form.code.data)
            db.session.add(a)
            db.session.commit()
            log_audit(current_user.id, 'creation_annee',
                      f'Année {a.code} créée', request.remote_addr)
            flash(f'Année « {a.libelle} » créée.', 'success')
            return redirect(url_for('referentiel.index', tab='annees'))
    return render_template('referentiel/form.html', form=form,
                           title='Ajouter une année académique')


@bp.route('/annees/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def annee_edit(id):
    a = AnneeAcademique.query.get_or_404(id)
    form = AnneeAcademiqueForm(obj=a)
    if form.validate_on_submit():
        dup = AnneeAcademique.query.filter(
            AnneeAcademique.code == form.code.data, AnneeAcademique.id != id).first()
        if dup:
            flash('Ce code est déjà utilisé.', 'danger')
        else:
            a.libelle = form.libelle.data
            a.code = form.code.data
            db.session.commit()
            log_audit(current_user.id, 'modification_annee',
                      f'Année {a.code} modifiée', request.remote_addr)
            flash(f'Année « {a.libelle} » mise à jour.', 'success')
            return redirect(url_for('referentiel.index', tab='annees'))
    return render_template('referentiel/form.html', form=form,
                           title=f'Modifier année « {a.libelle} »')


@bp.route('/annees/<int:id>/supprimer', methods=['POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def annee_delete(id):
    a = AnneeAcademique.query.get_or_404(id)
    if Releve.query.filter_by(annee_academique_id=id).count() > 0:
        flash(f'Impossible de supprimer « {a.libelle} » : des relevés y sont rattachés.', 'danger')
    else:
        Affectation.query.filter(
            (Affectation.annee_debut_id == id) | (Affectation.annee_fin_id == id)
        ).delete(synchronize_session='fetch')
        db.session.delete(a)
        db.session.commit()
        log_audit(current_user.id, 'suppression_annee',
                  f'Année {a.code} supprimée', request.remote_addr)
        flash(f'Année « {a.libelle} » supprimée.', 'success')
    return redirect(url_for('referentiel.index', tab='annees'))


# ── Classes ──────────────────────────────────────────────────────────────

@bp.route('/classes/ajouter', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def classe_add():
    form = ClasseForm()
    form.parcours_id.choices = [(p.id, f'{p.nom} ({p.code})') for p in
                                 Parcours.query.order_by(Parcours.nom).all()]
    if form.validate_on_submit():
        dup = Classe.query.filter_by(code=form.code.data.upper(),
                                      parcours_id=form.parcours_id.data).first()
        if dup:
            flash('Une classe avec ce code existe déjà dans ce parcours.', 'danger')
        else:
            c = Classe(nom=form.nom.data, code=form.code.data.upper(),
                       parcours_id=form.parcours_id.data)
            db.session.add(c)
            db.session.commit()
            log_audit(current_user.id, 'creation_classe',
                      f'Classe {c.code} créée', request.remote_addr)
            flash(f'Classe « {c.nom} » créée.', 'success')
            return redirect(url_for('referentiel.index', tab='classes'))
    return render_template('referentiel/form.html', form=form,
                           title='Ajouter une classe')


@bp.route('/classes/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def classe_edit(id):
    c = Classe.query.get_or_404(id)
    form = ClasseForm(obj=c)
    form.parcours_id.choices = [(p.id, f'{p.nom} ({p.code})') for p in
                                 Parcours.query.order_by(Parcours.nom).all()]
    if form.validate_on_submit():
        dup = Classe.query.filter(Classe.code == form.code.data.upper(),
                                   Classe.parcours_id == form.parcours_id.data,
                                   Classe.id != id).first()
        if dup:
            flash('Ce code est déjà utilisé dans ce parcours.', 'danger')
        else:
            c.nom = form.nom.data
            c.code = form.code.data.upper()
            c.parcours_id = form.parcours_id.data
            db.session.commit()
            log_audit(current_user.id, 'modification_classe',
                      f'Classe {c.code} modifiée', request.remote_addr)
            flash(f'Classe « {c.nom} » mise à jour.', 'success')
            return redirect(url_for('referentiel.index', tab='classes'))
    return render_template('referentiel/form.html', form=form,
                           title=f'Modifier classe « {c.nom} »')


@bp.route('/classes/<int:id>/supprimer', methods=['POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def classe_delete(id):
    c = Classe.query.get_or_404(id)
    if c.semestres.count() > 0 or Releve.query.filter_by(classe_id=id).count() > 0:
        flash(f'Impossible de supprimer « {c.nom} » : des semestres ou relevés y sont rattachés.', 'danger')
    else:
        db.session.delete(c)
        db.session.commit()
        log_audit(current_user.id, 'suppression_classe',
                  f'Classe {c.code} supprimée', request.remote_addr)
        flash(f'Classe « {c.nom} » supprimée.', 'success')
    return redirect(url_for('referentiel.index', tab='classes'))


# ── Semestres ────────────────────────────────────────────────────────────

@bp.route('/semestres/ajouter', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def semestre_add():
    form = SemestreForm()
    form.classe_id.choices = [
        (c.id, f'{c.nom} ({c.code}) — {c.parcours.nom}')
        for c in Classe.query.order_by(Classe.parcours_id, Classe.nom).all()
    ]
    if form.validate_on_submit():
        dup = Semestre.query.filter_by(code=form.code.data.upper(),
                                        classe_id=form.classe_id.data).first()
        if dup:
            flash('Un semestre avec ce code existe déjà dans cette classe.', 'danger')
        else:
            s = Semestre(nom=form.nom.data, code=form.code.data.upper(),
                         classe_id=form.classe_id.data)
            db.session.add(s)
            db.session.commit()
            log_audit(current_user.id, 'creation_semestre',
                      f'Semestre {s.code} créé', request.remote_addr)
            flash(f'Semestre « {s.nom} » créé.', 'success')
            return redirect(url_for('referentiel.index', tab='semestres'))
    return render_template('referentiel/form.html', form=form,
                           title='Ajouter un semestre')


@bp.route('/semestres/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def semestre_edit(id):
    s = Semestre.query.get_or_404(id)
    form = SemestreForm(obj=s)
    form.classe_id.choices = [
        (c.id, f'{c.nom} ({c.code}) — {c.parcours.nom}')
        for c in Classe.query.order_by(Classe.parcours_id, Classe.nom).all()
    ]
    if form.validate_on_submit():
        dup = Semestre.query.filter(Semestre.code == form.code.data.upper(),
                                     Semestre.classe_id == form.classe_id.data,
                                     Semestre.id != id).first()
        if dup:
            flash('Ce code est déjà utilisé dans cette classe.', 'danger')
        else:
            s.nom = form.nom.data
            s.code = form.code.data.upper()
            s.classe_id = form.classe_id.data
            db.session.commit()
            log_audit(current_user.id, 'modification_semestre',
                      f'Semestre {s.code} modifié', request.remote_addr)
            flash(f'Semestre « {s.nom} » mis à jour.', 'success')
            return redirect(url_for('referentiel.index', tab='semestres'))
    return render_template('referentiel/form.html', form=form,
                           title=f'Modifier semestre « {s.nom} »')


@bp.route('/semestres/<int:id>/supprimer', methods=['POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def semestre_delete(id):
    s = Semestre.query.get_or_404(id)
    if Releve.query.filter_by(semestre_id=id).count() > 0:
        flash(f'Impossible de supprimer « {s.nom} » : des relevés y sont rattachés.', 'danger')
    else:
        db.session.delete(s)
        db.session.commit()
        log_audit(current_user.id, 'suppression_semestre',
                  f'Semestre {s.code} supprimé', request.remote_addr)
        flash(f'Semestre « {s.nom} » supprimé.', 'success')
    return redirect(url_for('referentiel.index', tab='semestres'))


# ── Affectations ─────────────────────────────────────────────────────────

@bp.route('/affectations/ajouter', methods=['GET', 'POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def affectation_add():
    form = AffectationForm()
    _populate_affectation_choices(form)
    if form.validate_on_submit():
        # Contrôle anti-chevauchement (R17)
        if _check_overlap(form.parcours_id.data, form.annee_debut_id.data,
                          form.annee_fin_id.data or None):
            flash('Un autre chef est déjà affecté à ce parcours pour cette période.', 'danger')
        else:
            a = Affectation(
                utilisateur_id=form.utilisateur_id.data,
                parcours_id=form.parcours_id.data,
                annee_debut_id=form.annee_debut_id.data,
                annee_fin_id=form.annee_fin_id.data or None,
            )
            db.session.add(a)
            db.session.commit()
            log_audit(current_user.id, 'creation_affectation',
                      f'Affectation user={a.utilisateur_id} parcours={a.parcours_id}',
                      request.remote_addr)
            flash('Affectation créée.', 'success')
            return redirect(url_for('referentiel.index', tab='affectations'))
    return render_template('referentiel/form.html', form=form,
                           title='Ajouter une affectation')


@bp.route('/affectations/<int:id>/supprimer', methods=['POST'])
@login_required
@must_change_password
@role_required('directeur_etudes', 'admin')
def affectation_delete(id):
    a = Affectation.query.get_or_404(id)
    db.session.delete(a)
    db.session.commit()
    log_audit(current_user.id, 'suppression_affectation',
              f'Affectation id={id} supprimée', request.remote_addr)
    flash('Affectation supprimée.', 'success')
    return redirect(url_for('referentiel.index', tab='affectations'))


def _populate_affectation_choices(form):
    chefs = User.query.filter_by(role='chef_parcours', actif=True).order_by(User.nom).all()
    form.utilisateur_id.choices = [(u.id, f'{u.prenom} {u.nom}') for u in chefs]
    form.parcours_id.choices = [(p.id, f'{p.nom} ({p.code})') for p in
                                 Parcours.query.order_by(Parcours.nom).all()]
    annees = AnneeAcademique.query.order_by(AnneeAcademique.code).all()
    form.annee_debut_id.choices = [(a.id, a.libelle) for a in annees]
    form.annee_fin_id.choices = [(0, '— En cours —')] + [(a.id, a.libelle) for a in annees]


def _check_overlap(parcours_id, debut_id, fin_id, exclude_id=None):
    """Vérifie qu'aucune autre affectation ne chevauche la période pour ce parcours."""
    query = Affectation.query.filter_by(parcours_id=parcours_id)
    if exclude_id:
        query = query.filter(Affectation.id != exclude_id)

    for existing in query.all():
        # Logique de chevauchement simplifiée sur les IDs d'année
        # (on suppose que les IDs croissent avec le temps)
        e_start = existing.annee_debut_id
        e_end = existing.annee_fin_id  # None = en cours

        if e_end is None and fin_id is None:
            return True  # deux affectations "en cours"
        if e_end is None:
            if fin_id >= e_start:
                return True
        elif fin_id is None:
            if debut_id <= e_end:
                return True
        else:
            if debut_id <= e_end and fin_id >= e_start:
                return True
    return False
