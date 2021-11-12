import email
import email.message
import hashlib
import json
import os
import re
import select
import smtplib
import socket
from typing import NoReturn, Optional

import glosocket
import TP4_utils


class Server:

    def __init__(self) -> None:
        """
        Cette méthode est automatiquement appelée à l’instanciation du serveur, elle doit :
        - Initialiser le socket du serveur et le mettre en écoute. 
        - Créer le dossier des données pour le serveur dans le dossier courant s’il n’existe pas. 
        - Préparer deux listes vides pour les sockets clients.
        - Compiler un pattern Regex qui sera utilisé pour vérifier les adresses courriel.

        Attention : ne changez pas le nom des attributs fournis, ils sont utilisés dans les tests. 
        Vous pouvez cependant ajouter des attributs supplémentaires.
        """
        self._client_socket_list: list[socket.socket] = []
        self._connected_client_list: list[socket.socket] = []

        socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socket.bind(("localhost", 11037))
        socket.listen(5)
        self._server_socket = socket

        if(not os.path.isdir("data")):
            os.mkdir("data")
        self._server_data_path = "data"

        self._email_verificator = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

    def _recv_data(self, source: socket.socket) -> Optional[TP4_utils.GLO_message]:
        """
        Cette méthode utilise le module glosocket pour récupérer un message.
        Elle doit être appelée systématiquement pour recevoir des données d’un client.

        Le message attendu est une chaine de caractère représentant un JSON 
        valide, qui est décodé avec le module json. Si le JSON est invalide, 
        s’il ne représente pas un dictionnaire du format GLO_message, ou si 
        le résultat est None, le socket client est fermé et retiré des listes.
        """
        # TODO

    def _main_loop(self) -> None:
        """
        Boucle principale du serveur.

        Le serveur utilise le module select pour récupérer les sockets en 
        attente puis appelle l’une des méthodes _accept_client, _process_client
        ou _authenticate_client pour chacun d’entre eux.
        """
        # TODO
        (socket_client, adresse_client) = self._server_socket.accept()
        print(
            f"Connexion d'un nouveau client: {self._connected_client_list.count}")
        self._client_socket_list.append(socket_client)
        self._connected_client_list.append(adresse_client)

    def _accept_client(self) -> None:
        """
        Cette méthode accepte une connexion avec un nouveau socket client et 
        l’ajoute aux listes appropriées.
        """
        # TODO

    def _authenticate_client(self, client_socket: socket.socket) -> None:
        """
        Cette méthode traite les demandes de création de comptes et de connexion.

        Si les données reçues sont invalides, la méthode retourne immédiatement.
        Sinon, la méthode traite la requête et répond au client avec un JSON
        conformant à la classe d’annotation GLO_message. Si nécessaire, le client
        est également ajouté aux listes appropriées.
        """
        # TODO

    def _process_client(self, client_socket: socket.socket) -> None:
        """
        Cette méthode traite les commandes d’utilisateurs connectés.

        Si les données reçues sont invalides, la méthode retourne immédiatement.
        Sinon, la méthode traite la requête et répond au client avec un JSON
        conformant à la classe d’annotation GLO_message.
        """
        # TODO

    def _get_subject_list(self, username: str) -> TP4_utils.GLO_message:
        """
        Cette méthode récupère la liste des courriels d’un utilisateur.

        Le GLO_message retourné contient dans le champ "data" une liste
        de chaque sujet, sa source et un numéro (commence à 1).
        Si le nom d’utilisateur est invalide, le GLO_message retourné 
        indique l’erreur au client.
        """
        # TODO

    def _get_email(self, data: dict) -> TP4_utils.GLO_message:
        """
        Cette méthode récupère le contenu du courriel choisi par l’utilisateur.

        Le GLO_message retourné contient dans le champ « data » la représentation
        en chaine de caractère du courriel chargé depuis le fichier à l’aide du 
        module email. Si le choix ou le nom d’utilisateur est incorrect, le 
        GLO_message retourné indique l’erreur au client.
        """
        # TODO

    def _send_email(self, email_string: str) -> TP4_utils.GLO_message:
        """
        Cette méthode envoie un courriel local ou avec le serveur SMTP.

        Avant l’envoi, le serveur doit vérifier :
        - Les adresses courriel source et destination,
        - La source est un utilisateur existant.

        Selon le domaine de la destination, le courriel est envoyé à
        l’aide du serveur SMTP de l’université où il est écrit dans
        le dossier de destination.

        Le GLO_message retourné contient indique si l’envoi a réussi
        ou non.
        """
        # TODO

    def _get_stats(self, username: str) -> TP4_utils.GLO_message:
        """
        Cette méthode récupère les statistiques liées à un utilisateur.

        Le GLO_message retourné contient dans le champ « data » les entrées :
        - « count », avec le nombre de courriels,
        - « folder_size », avec la taille totale du dossier en octets.
        Si le nom d’utilisateur est invalide, le GLO_message retourné 
        indique l’erreur au client.
        """
        # TODO

    def run(self) -> NoReturn:
        """
        Appelle la méthode _main_loop en boucle jusqu’à la fin du programme.
        """
        while True:
            self._main_loop()


def main() -> NoReturn:
    Server().run()


if __name__ == "__main__":
    main()
