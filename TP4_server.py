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

        Attention: ne changez pas le nom des attributs fournis, ils sont utilisés dans les tests.
        Vous pouvez cependant ajouter des attributs supplémentaires.
        """
        self._client_socket_list: list[socket.socket] = []
        self._connected_client_list: list[socket.socket] = []
        self._client_count = 0

        socket_serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_serveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socket_serveur.bind(("127.0.0.1", TP4_utils.SOCKET_PORT))
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
        self.message = ""

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
        try:
            message = json.loads(message)
            if "header" not in message or "data" not in message:
                raise json.JSONDecodeError
        except (json.JSONDecodeError, TypeError):
            # Le json est invalide ou est none
            source.close()
            self._connected_client_list.remove(source)
            self._client_socket_list.remove(source)
            self._client_count -= 1
            return

        # Si on arrive ici, c'est que le json est valide et représente un GLO_message
        return TP4_utils.GLO_message(
            header=TP4_utils.message_header(message["header"]),
            data=message["data"]
        )

    def _main_loop(self) -> None:
        """
        Boucle principale du serveur.

        Le serveur utilise le module select pour récupérer les sockets en
        attente puis appelle l’une des méthodes _accept_client, _process_client
        ou _authenticate_client pour chacun d’entre eux.
        """
        while True:
            waiting_list, _, _ = select.select(
                [self._server_socket] + self._client_socket_list, [], []
            )

            for client in waiting_list:
                if client == self._server_socket:
                    self._accept_client()
                else:
                    self.message = self._recv_data(client)
                    if self.message["header"] == TP4_utils.message_header.AUTH_REGISTER or \
                            self.message["header"] == TP4_utils.message_header.AUTH_LOGIN:
                        self._authenticate_client(client)
                    self._process_client(client)

    def _accept_client(self) -> None:
        """
        Cette méthode accepte une connexion avec un nouveau socket client et
        l’ajoute aux listes appropriées.
        """
        client, _ = self._server_socket.accept()
        self._client_socket_list.append(client)
        self._client_count += 1
        print(f"Nouveau client connecté : {self._client_count}")

    def _authenticate_client(self, client_socket: socket.socket) -> None:
        """
        Cette méthode traite les demandes de création de comptes et de connexion.

        Si les données reçues sont invalides, la méthode retourne immédiatement.
        Sinon, la méthode traite la requête et répond au client avec un JSON
        conformant à la classe d’annotation GLO_message. Si nécessaire, le client
        est également ajouté aux listes appropriées.
        """
        message = self.message
        username = message["data"]["username"]
        password = message["data"]["password"]
        header = message["header"]

        user_datafile_path = self._server_data_path + username
        # Connexion
        if header == TP4_utils.message_header.AUTH_LOGIN:
            # Si le dossier correspondant au username n'existe pas, on retourne une erreur
            if not os.path.isdir(user_datafile_path):
                # Envoyer message erreur au client
                glosocket.send_msg(client_socket, json.dumps({
                    "header": TP4_utils.message_header.ERROR,
                    "data": "Nom d'utilisateur incorrect."
                }))
                return

            file = open(user_datafile_path + "/passwd", "r")
            content = file.read().replace('\n', '')
            if hashlib.sha384(password.encode()).hexdigest() != content:
                glosocket.send_msg(client_socket, json.dumps({
                    "header": TP4_utils.message_header.ERROR,
                    "data": "Mot de passe incorrect."
                }))
                return

            glosocket.send_msg(client_socket, json.dumps({
                "header": TP4_utils.message_header.OK,
                "data": {}
            }))
            self._connected_client_list.append(client_socket)

        # Création d'un compte
        if header == TP4_utils.message_header.AUTH_REGISTER:
            # On valide si le username est déjà prit
            if os.path.isdir(user_datafile_path):
                glosocket.send_msg(client_socket, json.dumps({
                    "header": TP4_utils.message_header.ERROR,
                    "data": "Le nom d'utilisateur est déjà prit."
                }))
                return

            # Valider sur le username et password sont invalide
            if re.search(r"^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])([a-zA-Z0-9]+){9,}$", password) is None:
                glosocket.send_msg(client_socket, json.dumps({
                    "header": TP4_utils.message_header.ERROR,
                    "data": "Le mot de passe doit contenir au moins 1 majuscule, 1 minuscule et 1 chiffre."
                }))
                return

            # Créer un fichier nommé 'passwd' dans user_datafile_path et encrypter le password dans le fichier
            if not os.path.isdir(user_datafile_path):
                os.mkdir(user_datafile_path)

            with open(user_datafile_path + "/passwd", "w") as file:
                file.write(hashlib.sha384(password.encode()).hexdigest())

            glosocket.send_msg(client_socket, json.dumps({
                "header": TP4_utils.message_header.OK,
                "data": {}
            }))
            self._connected_client_list.append(client_socket)

    def _process_client(self, client_socket: socket.socket) -> None:
        """
        Cette méthode traite les commandes d’utilisateurs connectés.

        Si les données reçues sont invalides, la méthode retourne immédiatement.
        Sinon, la méthode traite la requête et répond au client avec un JSON
        conformant à la classe d’annotation GLO_message.
        """
        message = self.message
        if message is None:
            self._connected_client_list.remove(client_socket)
            self._client_socket_list.remove(client_socket)
            self._client_count -= 1
            return

        action = message["header"]
        try:
            if action is TP4_utils.message_header.INBOX_READING_REQUEST:
                username = message["data"]["username"]
                glo_msg = self._get_subject_list(username)
                glosocket.send_msg(client_socket, json.dumps({
                    "header": glo_msg["header"],
                    "data": glo_msg["data"]
                }))
            elif action is TP4_utils.message_header.INBOX_READING_CHOICE:
                glo_msg = self._get_email(message["data"])
                glosocket.send_msg(client_socket, json.dumps({
                    "header": glo_msg["header"],
                    "data": glo_msg["data"]
                }))
            elif action is TP4_utils.message_header.EMAIL_SENDING:
                self._send_email(message["data"])
            elif action is TP4_utils.message_header.STATS_REQUEST:
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
        user_dir_path = self._server_data_path + username
        if os.path.isdir(user_dir_path):
            subjects = []
            for file in os.listdir(user_dir_path):
                # On valide si le fichier est du bon nom (si c'est un courriel)
                if re.search("^[1-9]+-" + username + "$", file) is not None:
                    with open(os.path.join(user_dir_path, file), "r") as f:
                        content = f.read()
                        # On récupère le sujet, le numéro et la source
                        number = file.split('-')[0]
                        subject = content.split('\\n')[2].split(' ')[1]
                        source = content.split('\\n')[0].split(' ')[1]
                        subjects.append(TP4_utils.SUBJECT_DISPLAY.format(number=number, subject=subject, source=source))
            return TP4_utils.GLO_message(header=TP4_utils.message_header.OK, data={"subjects": subjects})

        else:
            return TP4_utils.GLO_message(header=TP4_utils.message_header.ERROR, data=None)

    def _get_email(self, data: dict) -> TP4_utils.GLO_message:
        """
        Cette méthode récupère le contenu du courriel choisi par l’utilisateur.

        Le GLO_message retourné contient dans le champ «data» la représentation
        en chaine de caractère du courriel chargé depuis le fichier à l’aide du
        module email. Si le choix ou le nom d’utilisateur est incorrect, le
        GLO_message retourné indique l’erreur au client.
        if(usernameExists):
        """

        message = self.message
        username = message["data"]["username"]
        user_dir_path = self._server_data_path + username
        choix = message["data"]["choice"]

        filename = choix + '-' + username
        if os.path.isfile(os.path.join(user_dir_path, filename)):
            with open(os.path.join(user_dir_path, filename)) as f:
                formatted_content = f.read().split('\\n')
                source = formatted_content[0].split(' ')[1]
                destination = formatted_content[1].split(' ')[1]
                subject = formatted_content[2].split(' ')[1]
                content = formatted_content[-2]
                return TP4_utils.GLO_message(
                    header=TP4_utils.message_header.OK,
                    data={"source": source, "destination": destination, "subject": subject, "content": content}
                )
        else:
            return TP4_utils.GLO_message(
                header=TP4_utils.message_header.ERROR,
                data="Le numéro du courriel choisi est invalide."
            )

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
            return TP4_utils.GLO_message(header=TP4_utils.message_header.ERROR, data="L'adresse source n'existe pas")

        message = TP4_utils.GLO_message(
            header=TP4_utils.message_header.OK, data="Le courriel a été envoyé avec succès.")
        # Si l'adresse courriel de destination est une adresse ulaval
        if adresse_destination.split("@")[1] == "ulaval.ca":
            username_destination = adresse_destination.split("@")[0]
            dir_path = self._server_data_path + username_destination

            # Si l'utilisateur correspondant à l'adresse de destination est un utilisateur invalide
            if not os.path.isdir(self._server_data_path + username_destination):
                dir_path = self._server_lost_dir + username_destination
                if not os.path.isdir(dir_path):
                    os.mkdir(dir_path)

                message = TP4_utils.GLO_message(
                    header=TP4_utils.message_header.ERROR, data="L'adresse de destination n'existe pas")

            number_of_file_in_dir = len(
                [name for name in os.listdir(dir_path) if os.path.isfile(name)])
            filename = str(number_of_file_in_dir + 1) + username_destination

            file = open(dir_path + "/" + filename, "w")
            file.write(email_string)
            file.close()

            return message

        # On essaie de se connecter au serveur smtp distant pour envoyer le courriel
        destination_domain = adresse_destination.split("@")[1]
        smtp_server = "smtp." + destination_domain
        try:
            with smtplib.SMTP(smtp_server, timeout=10) as server:
                message = email.message_from_string(email_string)
                server.send_message(message)
                return TP4_utils.GLO_message(
                    header=TP4_utils.message_header.OK,
                    data="Le courriel a été envoyé avec succès."
                )
        except smtplib.smtplib.SMTPException:
            return TP4_utils.GLO_message(
                header=TP4_utils.message_header.ERROR,
                data="Le message n'a pas pu être envoyé"
            )
        except socket.timeout:
            return TP4_utils.GLO_message(
                header=TP4_utils.message_header.ERROR,
                data="La connexion au serveur SMTP n'a pas pu être établis"
            )

    def _get_stats(self, username: str) -> TP4_utils.GLO_message:
        """
        Cette méthode récupère les statistiques liées à un utilisateur.

        Le GLO_message retourné contient dans le champ « data » les entrées :
        - « count », avec le nombre de courriels,
        - « folder_size », avec la taille totale du dossier en octets.
        Si le nom d’utilisateur est invalide, le GLO_message retourné
        indique l’erreur au client.
        """

        # Compte le nombre de fichiers dans le dossier de l'utilisateur
        nombre_de_fichier = len([name for name in os.listdir(
            self._server_data_path + username) if os.path.isfile(name)])

        # Compte la taille du dossier de l'utilisateur
        taille_du_dossier = sum(
            os.path.getsize(self._server_data_path + username + "/" + name) for name in os.listdir(
                self._server_data_path + username) if os.path.isfile(name))

        return TP4_utils.GLO_message(
            header=TP4_utils.message_header.OK,
            data={"count": nombre_de_fichier, "size": taille_du_dossier}
        )

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
