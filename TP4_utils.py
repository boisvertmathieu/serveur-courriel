"""\
Module fournissant les entêtes, constantes et 
des gabarits pour l’affichage des courriels et
des statistiques.
"""
import enum
import os
from typing import Any, TypedDict

SOCKET_PORT = 5322
SERVER_DATA_DIR = f"server_data{os.sep}"
SERVER_LOST_DIR = f"LOST{os.sep}"
SERVER_DOMAIN = "glo-2000.ca"
SMTP_SERVER = "smtp.ulaval.ca"

CLIENT_AUTH_CHOICE = """1. Créer un compte
2. Se connecter"""
CLIENT_USE_CHOICE = """Menu principal
1. Consultation de courriels
2. Envoi de courriels
3. Statistiques
4. Quitter"""

SUBJECT_DISPLAY = "n°{number} {subject} - {source}"

EMAIL_DISPLAY = """De : {source}
À : {destination}
Sujet : {subject}
----------------------------------------
{content}
"""

STATS_DISPLAY = """Nombre de messages : {count}
Taille du dossier : {size} octets"""


class message_header(enum.IntEnum):
    """
    Entêtes à utiliser pour échanger des messages entre le client et le serveur.
    """
    OK = enum.auto()
    ERROR = enum.auto()

    AUTH_REGISTER = enum.auto()
    AUTH_LOGIN = enum.auto()

    INBOX_READING_REQUEST = enum.auto()
    INBOX_READING_CHOICE = enum.auto()

    EMAIL_SENDING = enum.auto()

    STATS_REQUEST = enum.auto()


class GLO_message(TypedDict, total=True):
    """
    Format de dictionnaire à utiliser pour les échanges.
    """
    header: message_header
    data: Any
