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
        self._client_count = 0

        socket_serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_serveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socket_serveur.bind(("localhost", TP4_utils.SOCKET_PORT))
        socket_serveur.listen(5)
        self._server_socket = socket_serveur

        if not os.path.isdir(TP4_utils.SERVER_DATA_DIR):
            os.mkdir(TP4_utils.SERVER_DATA_DIR)
        if not os.path.isdir(TP4_utils.SERVER_LOST_DIR):
            os.mkdir(TP4_utils.SERVER_LOST_DIR)
        self._server_data_path = TP4_utils.SERVER_DATA_DIR
        self._server_lost_dir = TP4_utils.SERVER_LOST_DIR

        self._email_verificator = re.compile(
            r"\b[A-Za-z0-9._%+-]+@ulaval\.ca")

    def _recv_data(self, source: socket.socket) -> Optional[TP4_utils.GLO_message]:
        """
        Cette méthode utilise le module glosocket pour récupérer un message.
        Elle doit être appelée systématiquement pour recevoir des données d’un client.

        Le message attendu est une chaine de caractère représentant un JSON
        valide, qui est décodé avec le module json. Si le JSON est invalide,
        s’il ne représente pas un dictionnaire du format GLO_message, ou si
        le résultat est None, le socket client est fermé et retiré des listes.
        """
        message = glosocket.recv_msg(source)
        if message is None:
            source.close()
            self._connected_client_list.remove(source)
            self._client_socket_list.remove(source)
            self._client_count -= 1
        else:
            try:
                # TODO : Valider si data est de type GLO_message
                json_data = json.loads(message)
                data = TP4_utils.GLO_message(header=json_data["header"], data={
                                             "username": json_data["username"], "password": json_data["password"]})

                # Retourner les données contenu dans data sous forme de GLO_message
                return data
            except json.JSONDecodeError:
                return

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
            if client == self._server_socket:
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
        self._client_count += 1
        print(f"Nouveau client connecté : {self._client_count}")

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
        data = self._recv_data(client_socket)
        username = data["data"]["password"]
        password = data["data"]["username"]
        header = data["header"]

        user_datafile_path = self._server_data_path + username
        # Connexion
        if header == TP4_utils.message_header.AUTH_LOGIN:
            # On valide si un fichier correspondant au username existe
            if not os.path.isfile(user_datafile_path):
                # Envoyer message erreur au client
                glosocket.send_msg(client_socket, json.dumps({
                    "header": TP4_utils.message_header.ERROR,
                    "data": {
                        "message": "Nom d'utilisateur incorrect."
                    }
                }))
            else:
                file = open(user_datafile_path + "/passwd", "r")
                content = file.read().replace('\n', '')
                if hashlib.sha384(password.encode()).hexdigest() != content:
                    glosocket.send_msg(client_socket, json.dumps({
                        "header": TP4_utils.message_header.ERROR,
                        "data": {
                            "message": "Mot de passe incorrect."
                        }
                    }))
                else:
                    glosocket.send_msg(client_socket, json.dumps({
                        "header": TP4_utils.message_header.OK, "data": {}
                    }))

                file.close()

        # Création d'un compte
        elif header == TP4_utils.message_header.AUTH_REGISTER:
            # On valide si le username est déjà prit
            if os.path.isdir(user_datafile_path):
                glosocket.send_msg(client_socket, json.dumps({
                    "header": TP4_utils.message_header.ERROR,
                    "data": {
                        "message": "Le nom d'utilisateur est déjà prit."
                    }}))
            # Valider sur le username et password sont invalide
            elif re.search(r"^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])([a-zA-Z0-9]+){9,}$", password) is None:
                glosocket.send_msg(client_socket, json.dumps({
                    "header": TP4_utils.message_header.ERROR,
                    "data": {
                        "message": "Le mot de passe doit contenir au moins 1 majuscule, 1 minuscule et 1 chiffre."
                    }
                }))
            else:
                # Créer un fichier nommé 'passwd' dans user_datafile_path et encrypter le password dans le fichier
                file = open(user_datafile_path + "/passwd", "w")
                file.write(hashlib.sha384(password.encode()).hexdigest())
                file.close()

                glosocket.send_msg(client_socket, json.dumps({
                    "header": TP4_utils.message_header.OK,
                    "data": {}
                }))

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
            try:
                if(action is TP4_utils.message_header.INBOX_READING_REQUEST):
                    username = message["data"]["username"]
                    self._get_subject_list(username)
                elif(action is TP4_utils.message_header.INBOX_READING_CHOICE):
                    self._get_email(message["data"])
                elif(action is TP4_utils.message_header.EMAIL_SENDING):
                    self._send_email(message["data"])
                elif(action is TP4_utils.message_header.STATS_REQUEST):
                    username = message["data"]["username"]
                    self._get_stats(username)
            except Exception as ex:
                glosocket.send_msg(client_socket, json.dumps({
                    "header": TP4_utils.message_header.ERROR,
                    "data": ex
                }))

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
        if(usernameExists):
        """
        usernameExists = os.path.isdir("./server_data/{username}")
        if(usernameExists):

            emailExists = os.path.isfile("./server_data/{username}/" + data)
            if(emailExists):
                with open("./server_data/{username}/{email}") as file:
                    """utiliser os pour prendre les infos du email"""
                    number = ""
                    subject = ""
                    source = ""

                    file = open("./server_data/{username}/{email}", "r")
                    content = file.read()
                    file.close()
                    retour = TP4_utils.EMAIL_DISPLAY.format(
                        number=number, subject=subject, source=source, content=content)
                    return TP4_utils.GLO_message(header=TP4_utils.message_header.OK, data=retour)
            else:
                return TP4_utils.GLO_message(header=TP4_utils.message_header.Error, data="Le message n'existe pas")
        else:
            return TP4_utils.GLO_message(header=TP4_utils.message_header.ERROR, data="Cet utilisateur n'existe pas")

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
        adresse_source = email_string.split("\n")[0].split(" ")[1]
        adresse_destination = email_string.split("\n")[1].split(" ")[1]

        # On vérifie si l'adresse source correspond à un utilisateur valide
        username_source = adresse_source.split("@")[0]
        if not os.path.isdir(self._server_data_path + username_source):
            raise Exception(
                "Aucun utilisateur existant n'est associé à l'adresse source.")

        # Si l'adresse courriel de destination est une adresse ulaval
        if adresse_destination.split("@")[1] == "ulaval.ca":
            username_destination = adresse_destination.split("@")[0]
            dir_path = self._server_data_path + username_destination
            throw_ex = False

            # Si l'utilisateur correspondant à l'adresse de destination est un utilisateur invalide
            if not os.path.isdir(self._server_data_path + username_destination):
                throw_ex = True
                dir_path = self._server_lost_dir + username_destination
                if not os.path.isdir(dir_path):
                    os.mkdir(dir_path)

            number_of_file_in_dir = len(
                [name for name in os.listdir(dir_path) if os.path.isfile(name)])
            filename = str(number_of_file_in_dir + 1) + username_destination

            file = open(dir_path + "/" + filename, "w")
            file.write(email_string)
            file.close()

            # Si l'utilisateur de destination était un utilisateur invalide, on retourne un message d'erreur
            if throw_ex:
                raise Exception("Adresse courriel de destinataire invalide.")
        else:
            # On essaie de se connecter au serveur smtp distant pour envoyer le courriel
            destination_domain = adresse_destination.split("@")[1]
            smtp_server = "smtp." + destination_domain

            try:
                with smtplib.SMTP(smtp_server, timeout=10) as server:
                    message = email.message_from_string(email_string)
                    server.send_message(message)
            except smtplib.smtplib.SMTPException:
                raise Exception("Le message n'a pas pu être envoyé")
            except socket.timeout:
                raise Exception(
                    "La connexion au serveur SMTP n'a pas pu être établis")

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
