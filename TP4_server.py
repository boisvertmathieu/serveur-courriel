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
        self.client_count = 0

        socket_serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_serveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socket_serveur.bind(("localhost", TP4_utils.SOCKET_PORT))
        socket_serveur.listen(5)
        self._server_socket = socket_serveur

        if(not os.path.isdir(TP4_utils.SERVER_DATA_DIR)):
            os.mkdir(TP4_utils.SERVER_DATA_DIR)
        self._server_data_path = TP4_utils.SERVER_DATA_DIR

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

        answer = json.loads(glosocket.recv_msg(self._socket))
        if(answer.get("header") == TP4_utils.message_header.OK and answer.get("data") is not None):
            message = TP4_utils.GLO_message(
                header=answer["header"],
                data=answer["data"]
            )
            return message
        else:
            source.close()
            self._connected_client_list.remove(source)
            self._client_socket_list.remove(source)

    def _main_loop(self) -> None:
        """
        Boucle principale du serveur.

        Le serveur utilise le module select pour récupérer les sockets en 
        attente puis appelle l’une des méthodes _accept_client, _process_client
        ou _authenticate_client pour chacun d’entre eux.
        """
        waiting_list, _, _ = select.select(
            [self._server_socket] + self._client_socket_list, [], []
        )

        for client in waiting_list:
            if(client == self._server_socket):
                self._accept_client(client)
            else:
                # On traite le client
                message = glosocket.recv_msg(client)
                # Si le client s'est déconnecté
                if(message is None):
                    self._client_socket_list.remove(client)
                    self._connected_client_list.remove(client)
                    self.client_count -= 1
                    return
                # On récupère l'entête du socket et on traite correctement le client
                header, data = message.split(maxsplit=1)
                if(header == TP4_utils.message_header.AUTH_REGISTER or
                   header == TP4_utils.message_header.AUTH_LOGIN):
                    self._authenticate_client(client)
                else:
                    self._process_client(client)

    def _accept_client(self) -> None:
        """
        Cette méthode accepte une connexion avec un nouveau socket client et 
        l’ajoute aux listes appropriées.
        """
        # On traite le nouveau client
        client, _ = self._server_socket.accept()
        self._client_socket_list.append(client)
        self._connected_client_list.append(client)
        self.client_count += 1
        print(f"Nouveau client connecté : {self.client_count}")

        glosocket.send_msg(client, "Bonjour")
        return

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
        message = glosocket.recv_msg(client_socket)
        if(message is not None):
            action = message["header"]
            if(action is TP4_utils.message_header.INBOX_READING_REQUEST):
                username = message["data"]["username"]
                self._get_subject_list(username)
            elif(action is TP4_utils.INBOX_READING_CHOICE):
                self._get_email(message["data"])
            elif(action is TP4_utils.EMAIL_SENDING):
                self._send_email(message["data"])
            elif(action is TP4_utils.STATS_REQUEST):
                username = message["data"]["username"]
                self._get_stats(username)

    def _get_subject_list(self, username: str) -> TP4_utils.GLO_message:
        """
        Cette méthode récupère la liste des courriels d’un utilisateur.

        Le GLO_message retourné contient dans le champ "data" une liste
        de chaque sujet, sa source et un numéro (commence à 1).
        Si le nom d’utilisateur est invalide, le GLO_message retourné 
        indique l’erreur au client.
        """
        usernameExists = os.path.isdir("./server_data/{username}")
        if(usernameExists):
            emails = os.listdir("./server_data/{username}")
            retour: dict
            for email in emails:
                """utiliser os pour prendre les infos de chaque email"""
                number = ""
                subject = ""
                source = ""
                retour[number] = TP4_utils.SUBJECT_DISPLAY.format(
                    number=number, subject=subject, source=source)

            return TP4_utils.GLO_message(header=TP4_utils.message_header.OK, data=retour)
        else:
            return TP4_utils.GLO_message(header=TP4_utils.message_header.ERROR, data=None)

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
