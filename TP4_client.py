import argparse
import email
import email.message
import getpass
import json
import re
import socket
from typing import NoReturn

import glosocket
import TP4_utils


class Client:

    def __init__(self, destination: str) -> None:
        """
        Cette méthode est automatiquement appelée à l’instanciation du client,
        elle doit:
        - Initialiser le socket du client et le connecter à l’adresse en paramètre.
        - Préparer un attribut «_logged_in» pour garder en mémoire l’état de
            l’authentification avec le serveur.
        - Préparer un attribut «_username» pour garder en mémoire le nom
            d’utilisateur utilisé pour l’authentification.

        Attention: ne changez pas le nom des attributs fournis, ils sont utilisés dans les tests.
        Vous pouvez cependant ajouter des attributs supplémentaires.
        """
        self._logged_in = False
        self._username = ""

        soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        soc.connect((destination, TP4_utils.SOCKET_PORT))

        self.socket_client = soc

    def _recv_data(self) -> TP4_utils.GLO_message:
        """
        Cette fonction utilise le module glosocket pour récupérer un message.
        Elle doit être appelée systématiquement pour recevoir des données du serveur.

        Le message attendu est une chaine de caractère représentant un GLO_message
        valide, qui est décodé avec le module json. Si le JSON est invalide
        ou le résultat est None, le programme termine avec un code-1.
        """
        message = glosocket.recv_msg(self.socket_client)
        try:
            message = json.loads(message)
            if message["header"] is None or message["data"] is None:
                raise json.JSONDecodeError
        except (json.JSONDecodeError, TypeError):
            exit(-1)

        return TP4_utils.GLO_message(
            header=TP4_utils.message_header(message["header"]),
            data=message["data"]
        )

    def _authentication(self) -> None:
        """
        Cette fonction traite l’authentification du client.

        La fonction, dans l’ordre:
        - Demande au client s’il souhaite se connecter ou créer un compte
        - Demande le nom d’utilisateur
        - Demande le mot de passe
        - Transmet la requête au serveur
        - Traite la réponse du serveur
        """
        while True:
            choix: str = input(TP4_utils.CLIENT_AUTH_CHOICE + "\n")
            if re.search(r"^1|2$", choix) is not None:
                # Connexion ou création de l'utilisateur
                username: str = input("\nEntrez votre nom d'utilisateur: ")
                password = getpass.getpass("Entrez votre mot de passe: ")

                header = TP4_utils.message_header.AUTH_REGISTER
                if choix == "2":
                    header = TP4_utils.message_header.AUTH_LOGIN

                glosocket.send_msg(self.socket_client, json.dumps({
                    "header": header,
                    "data": {"username": username, "password": password}
                }))

                message = self._recv_data()
                if message["header"] == TP4_utils.message_header.ERROR:
                    print("\n" + message["data"] + "\n")
                else:
                    self._logged_in = True
                    self._username = username
                    return
            else:
                print("\nSélection invalide.\n")

    def _main_loop(self) -> None:
        """
        Cette fonction traite les actions du client après authentification.

        La fonction affiche le menu principal à l’utilisateur, récupère son
        choix et appelle l’une des fonctions _reading, _sending ou _get_stats
        ou quitte avec un code0.
        """
        while True:
            choix: str = input("\n" + TP4_utils.CLIENT_USE_CHOICE + "\n")
            if re.search(r"^1|2|3|4$", choix) is not None:
                if choix == "1":
                    self._reading()
                elif choix == "2":
                    self._sending()
                elif choix == "3":
                    self._get_stats()
                elif choix == "4":
                    exit(0)
            else:
                print("\nSélection invalide.\n")

    def _reading(self) -> None:
        """
        Cette fonction traite les requêtes de consultation de courriel.

        La fonction, dans l’ordre:
        - Envoie une requête au serveur de consultation de courriel.
        - Récupère la liste des sujets depuis le serveur.
        - Demande à l’utilisateur quel courriel consulter.
        - Transmet ce choix au serveur.
        - Récupère le courriel choisi depuis le serveur.
        - Affiche le courriel dans le terminal avec le gabarit EMAIL_DISPLAY.
        """
        glosocket.send_msg(self.socket_client, json.dumps({
            "header": TP4_utils.message_header.INBOX_READING_REQUEST,
            "data": {"username": self._username}
        }))

        message = self._recv_data()
        if message["header"] == TP4_utils.message_header.ERROR:
            print("\nErreur lors de la récupération des courriels.\n")
            return

        if not len(message["data"]["subjects"]):
            print("\nIl y a aucun courriels.\n")
            return

        print("\nListe des sujets: ")
        for subject in message["data"]["subjects"]:
            print(subject)
        print("\n(Si plusieurs numéros, séparez ceux-ci par une virgule. Ex: 1,2,3,4)")
        choix: str = input("Entrez les numéros de courriel que vous souhaitez consulter: ")

        if re.search(r"^[0-9]+(,[0-9]+)*$", choix) is None:
            print("\nErreur lors du choix des courriels disponibles.\n")
            return

        glosocket.send_msg(self.socket_client, json.dumps({
            "header": TP4_utils.message_header.INBOX_READING_CHOICE,
            "data": {"username": self._username, "choice": choix}
        }))

        message = self._recv_data()
        if message["header"] == TP4_utils.message_header.ERROR:
            print("\nErreur lors de la récupération des courriels.\n")
            return
        for courriel in message["data"]:
            print(TP4_utils.EMAIL_DISPLAY.format(**courriel))

    def _sending(self) -> None:
        """
        Cette fonction traite les requêtes d’envoi de courriel.

        Cette fonction, dans l’ordre:
        - Demande l’adresse email de destination
        - Demande le sujet
        - Demande le contenu du message.
        - Avec ces informations, crée un objet EmailMessage
        - Envoie l’objet sous forme de chaine de caractère au serveur
        - Récupère la réponse du serveur, affiche l’erreur si nécessaire

        Note: un utilisateur termine la saisie avec un point sur une
        ligne
        """
        destinataire = input("Adresse du destinataire: ")
        sujet = input("Sujet du message: ")
        corps = ""
        buffer = ""
        while buffer != ".":
            corps += buffer
            buffer = input("") + '\n'

        message = email.message.EmailMessage()
        message["From"] = self._username + "@ulaval.ca"
        message["To"] = destinataire
        message["Subject"] = sujet
        message.set_content(corps)

        glosocket.send_msg(self.socket_client, json.dumps({
            "header": TP4_utils.message_header.EMAIL_SENDING,
            "data": message.as_string()
        }))

        # TODO : Valider si le serveur repond avec une erreur, si oui, on affiche l'erreur avant la fin de la fonction

    def _get_stats(self) -> None:
        """
        Cette fonction traite les requêtes de demandes de statistiques.

        Cette fonction, dans l’ordre:
        - Envoie une requête de statistique au serveur.
        - Récupère les statistiques depuis le serveur.
        - Affiche les statistiques dans le terminal avec le gabarit
            STATS_DISPLAY.
        """

        glosocket.send_msg(self.socket_client, json.dumps({
            "header": TP4_utils.message_header.STATS_REQUEST,
        }))

        message = self._recv_data()
        if message["header"] == TP4_utils.message_header.ERROR:
            print(message["data"])
            return

        print(TP4_utils.STATS_DISPLAY.format(**message["data"]))

    def run(self) -> NoReturn:
        """
        Appelle la fonction _athentication en boucle jusqu’à la connexion.
        Une fois connecté, appelle la fonction _main_loop en boucle jusqu’à
        la fin du programme.
        """
        while not self._logged_in:
            self._authentication()
        while True:
            self._main_loop()


def main() -> NoReturn:
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--destination",
                        dest="destination", type=str, action="store", required=True)
    destination = parser.parse_args().destination
    Client(destination).run()


if __name__ == '__main__':
    main()
