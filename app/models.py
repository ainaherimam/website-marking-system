from datetime import datetime, timezone

import bcrypt
from flask_login import UserMixin

from app import db, login_manager


# ---------------------------------------------------------------------------
# Utilisateur
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = 'utilisateur'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    mot_de_passe = db.Column(db.LargeBinary, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # chef_parcours, directeur_etudes, admin
    actif = db.Column(db.Boolean, default=True, nullable=False)
    doit_changer_mdp = db.Column(db.Boolean, default=True, nullable=False)
    date_creation = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    affectations = db.relationship('Affectation', backref='utilisateur', lazy='dynamic')
    releves_deposes = db.relationship('Releve', backref='deposeur', lazy='dynamic')

    def set_password(self, password):
        self.mot_de_passe = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.mot_de_passe)

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Référentiel académique
# ---------------------------------------------------------------------------

class Parcours(db.Model):
    __tablename__ = 'parcours'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)

    classes = db.relationship('Classe', backref='parcours', lazy='dynamic')
    affectations = db.relationship('Affectation', backref='parcours', lazy='dynamic')

    def __repr__(self):
        return f'<Parcours {self.code}>'


class AnneeAcademique(db.Model):
    __tablename__ = 'annee_academique'

    id = db.Column(db.Integer, primary_key=True)
    libelle = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)

    def __repr__(self):
        return f'<AnneeAcademique {self.code}>'


class Classe(db.Model):
    __tablename__ = 'classe'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    parcours_id = db.Column(db.Integer, db.ForeignKey('parcours.id'), nullable=False)

    semestres = db.relationship('Semestre', backref='classe', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('code', 'parcours_id', name='uq_classe_code_parcours'),
    )

    def __repr__(self):
        return f'<Classe {self.code}>'


class Semestre(db.Model):
    __tablename__ = 'semestre'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(10), nullable=False)
    classe_id = db.Column(db.Integer, db.ForeignKey('classe.id'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('code', 'classe_id', name='uq_semestre_code_classe'),
    )

    def __repr__(self):
        return f'<Semestre {self.code}>'


# ---------------------------------------------------------------------------
# Affectation Chef de Parcours
# ---------------------------------------------------------------------------

class Affectation(db.Model):
    __tablename__ = 'affectation'

    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    parcours_id = db.Column(db.Integer, db.ForeignKey('parcours.id'), nullable=False)
    annee_debut_id = db.Column(db.Integer, db.ForeignKey('annee_academique.id'), nullable=False)
    annee_fin_id = db.Column(db.Integer, db.ForeignKey('annee_academique.id'), nullable=True)

    annee_debut = db.relationship('AnneeAcademique', foreign_keys=[annee_debut_id])
    annee_fin = db.relationship('AnneeAcademique', foreign_keys=[annee_fin_id])

    def __repr__(self):
        return f'<Affectation user={self.utilisateur_id} parcours={self.parcours_id}>'


# ---------------------------------------------------------------------------
# Relevé de Notes
# ---------------------------------------------------------------------------

class Releve(db.Model):
    __tablename__ = 'releve'

    id = db.Column(db.Integer, primary_key=True)
    classe_id = db.Column(db.Integer, db.ForeignKey('classe.id'), nullable=False)
    semestre_id = db.Column(db.Integer, db.ForeignKey('semestre.id'), nullable=False)
    annee_academique_id = db.Column(db.Integer, db.ForeignKey('annee_academique.id'), nullable=False)
    parcours_id = db.Column(db.Integer, db.ForeignKey('parcours.id'), nullable=False)
    fichier_chemin = db.Column(db.String(500), nullable=False)
    nom_fichier_original = db.Column(db.String(300), nullable=False)
    taille_fichier = db.Column(db.Integer, nullable=False)
    date_depot = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    depose_par_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)

    classe = db.relationship('Classe', backref='releves')
    semestre = db.relationship('Semestre', backref='releves')
    annee_academique = db.relationship('AnneeAcademique', backref='releves')
    parcours = db.relationship('Parcours', backref='releves')

    __table_args__ = (
        db.UniqueConstraint('classe_id', 'semestre_id', 'annee_academique_id', 'parcours_id',
                            name='uq_releve_unique'),
    )

    def __repr__(self):
        return f'<Releve {self.nom_fichier_original}>'


# ---------------------------------------------------------------------------
# Journal d'Audit
# ---------------------------------------------------------------------------

class AuditLog(db.Model):
    __tablename__ = 'journal_audit'

    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    adresse_ip = db.Column(db.String(45), nullable=True)
    date_heure = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    utilisateur = db.relationship('User', backref='audit_logs')

    def __repr__(self):
        return f'<AuditLog {self.action} @ {self.date_heure}>'


# ---------------------------------------------------------------------------
# Paramètres Système
# ---------------------------------------------------------------------------

class ParametreSysteme(db.Model):
    __tablename__ = 'parametre_systeme'

    id = db.Column(db.Integer, primary_key=True)
    cle = db.Column(db.String(100), unique=True, nullable=False)
    valeur = db.Column(db.String(500), nullable=False)

    def __repr__(self):
        return f'<Parametre {self.cle}={self.valeur}>'
