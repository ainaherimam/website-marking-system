import click
from flask import current_app
from app import db
from app.models import User, ParametreSysteme


def register_commands(app):

    @app.cli.command('init-db')
    def init_db():
        """Crée les tables et les comptes par défaut."""
        db.create_all()
        click.echo('Tables créées.')

        # Compte Admin
        if not User.query.filter_by(email='admin').first():
            admin = User(
                nom='Administrateur',
                prenom='Système',
                email='admin',
                role='admin',
                actif=True,
                doit_changer_mdp=True,
            )
            admin.set_password('admin')
            db.session.add(admin)
            click.echo('Compte admin créé (login: admin / mdp: admin)')

        # Compte Directeur des Études
        if not User.query.filter_by(email='directeur').first():
            directeur = User(
                nom='Directeur',
                prenom='Des Études',
                email='directeur',
                role='directeur_etudes',
                actif=True,
                doit_changer_mdp=True,
            )
            directeur.set_password('1234')
            db.session.add(directeur)
            click.echo('Compte directeur créé (login: directeur / mdp: 1234)')

        # Paramètres système par défaut
        defaults = {
            'taille_max_fichier_mo': '10',
            'timeout_session_minutes': '30',
        }
        for cle, valeur in defaults.items():
            if not ParametreSysteme.query.filter_by(cle=cle).first():
                db.session.add(ParametreSysteme(cle=cle, valeur=valeur))

        db.session.commit()
        click.echo('Initialisation terminée.')
