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
                raise Exception()
        except Exception as ex:
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
                elif client in self._connected_client_list:
                    self._process_client(client)
                else:
                    self._authenticate_client(client)

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
        message = self._recv_data(client_socket)
        username: str = message["data"]["username"]
        password: str = message["data"]["password"]
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
                    "data": "Le nom d'utilisateur est déjà pris."
                }))
                return

            # Valider sur le username et password sont invalide
            if re.search(r"\s", username) is not None:
                glosocket.send_msg(client_socket, json.dumps({
                    "header": TP4_utils.message_header.ERROR,
                    "data": "Le nom d'utilisateur ne doit pas contenir d'espace."
                }))
                return

            if re.search(r"(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])", password) is None:
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
        message = self._recv_data(client_socket)

        # Si le client s'est déconnecté
        if message is None:
            return

        header = message["header"]
        glo_msg = {}
        try:
            if header is TP4_utils.message_header.INBOX_READING_REQUEST:
                glo_msg = self._get_subject_list(message["data"]["username"])
            elif header is TP4_utils.message_header.INBOX_READING_CHOICE:
                glo_msg = self._get_email(message["data"])
            elif header is TP4_utils.message_header.EMAIL_SENDING:
                glo_msg = self._send_email(message["data"])
            elif header is TP4_utils.message_header.STATS_REQUEST:
                glo_msg = self._get_stats(message["data"]["username"])

            glosocket.send_msg(client_socket, json.dumps({
                "header": glo_msg["header"],
                "data": glo_msg["data"]
            }))
        except Exception as ex:
            glo_msg["header"] = TP4_utils.message_header.ERROR
            glo_msg["data"] = ex

    def _get_subject_list(self, username: str) -> TP4_utils.GLO_message:
        """
        Cette méthode récupère la liste des courriels d’un utilisateur.

        Le GLO_message retourné contient dans le champ "data" une liste
        de chaque sujet, sa source et un numéro (commence à 1).
        Si le nom d’utilisateur est invalide, le GLO_message retourné
        indique l’erreur au client.
        """
        user_dir_path = os.path.join(self._server_data_path, username)
        if os.path.isdir(user_dir_path):
            subjects = []
            for file in os.listdir(user_dir_path):
                # On valide si le fichier est du bon nom (si c'est un courriel)
                if re.search(f"^[1-9]+-{username}$", file) is not None:
                    with open(os.path.join(user_dir_path, file), "r") as f:
                        content = f.read()
                        # On récupère le sujet, le numéro et la source
                        number = file.split('-')[0]
                        subject = content.split('\n')[2].split(' ')[1]
                        source = content.split('\n')[0].split(' ')[1]
                        subjects.append(TP4_utils.SUBJECT_DISPLAY.format(
                            number=number, subject=subject, source=source))
            return TP4_utils.GLO_message(header=TP4_utils.message_header.OK, data={"subjects": subjects})
        else:
            return TP4_utils.GLO_message(header=TP4_utils.message_header.ERROR, data={})

    def _get_email(self, data: dict) -> TP4_utils.GLO_message:
        """
        Cette méthode récupère le contenu du courriel choisi par l’utilisateur.

        Le GLO_message retourné contient dans le champ «data» la représentation
        en chaine de caractère du courriel chargé depuis le fichier à l’aide du
        module email. Si le choix ou le nom d’utilisateur est incorrect, le
        GLO_message retourné indique l’erreur au client.
        if(usernameExists):
        """

        username = data["username"]
        choix = data["choice"]
        user_dir_path = os.path.join(self._server_data_path, username)
        filename = choix + '-' + username

        if os.path.isfile(os.path.join(user_dir_path, filename)):
            with open(os.path.join(user_dir_path, filename)) as f:
                formatted_content = f.read().split('\n')
                source = formatted_content[0].split(' ')[1]
                destination = formatted_content[1].split(' ')[1]
                subject = formatted_content[2].split(' ')[1]
                content = '\n'.join(formatted_content[6:])

                return TP4_utils.GLO_message(
                    header=TP4_utils.message_header.OK,
                    data={"source": source, "destination": destination,
                          "subject": subject, "content": content}
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

        # On vérifie si les adresses courriels sont valides
        if (re.search(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", adresse_source) is None):
            return TP4_utils.GLO_message(
                header=TP4_utils.message_header.ERROR,
                data="L'adresse source n'est pas une adresse courriel valide."
            )

        if (re.search(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", adresse_destination) is None):
            return TP4_utils.GLO_message(
                header=TP4_utils.message_header.ERROR,
                data="L'adresse destination n'est pas une adresse courriel valide."
            )

        # On vérifie si l'adresse source n'est pas un utilisateur valide
        username_source = adresse_source.split("@")[0]
        if not os.path.isdir(self._server_data_path + username_source):
            return TP4_utils.GLO_message(header=TP4_utils.message_header.ERROR, data="L'adresse source n'existe pas")

        message = TP4_utils.GLO_message(
            header=TP4_utils.message_header.OK, data="Le courriel a été envoyé avec succès.")

        # Si l'adresse courriel de destination est une adresse glo-2000
        destination_domain = adresse_destination.split("@")[1]
        if destination_domain == TP4_utils.SERVER_DOMAIN:
            username_destination = adresse_destination.split("@")[0]
            dir_path = os.path.join(
                self._server_data_path, username_destination)

            # Si l'utilisateur correspondant à l'adresse de destination est un utilisateur invalide
            if not os.path.isdir(dir_path):
                dir_path = self._server_lost_dir + username_destination
                if not os.path.isdir(dir_path):
                    os.mkdir(dir_path)

                message = TP4_utils.GLO_message(
                    header=TP4_utils.message_header.ERROR, data="L'adresse de destination n'existe pas")

            # trouver le numeros du courriel et ne pas compter le fichier du mot de passe
            number_of_file_in_dir = len(os.listdir(dir_path)) - 1
            print(
                f"Number of file in destination user dir: {number_of_file_in_dir}")
            filename = str(number_of_file_in_dir + 1) + \
                '-' + username_destination

            with open(os.path.join(dir_path, filename), "w") as f:
                f.write(email_string)

            return message

        # On essaie de se connecter au serveur smtp distant pour envoyer le courriel externe
        destination_domain = adresse_destination.split("@")[1]
        try:
            with smtplib.SMTP(host=TP4_utils.SMTP_SERVER, timeout=10) as server:
                message = email.message_from_string(email_string)
                server.send_message(message)
                return TP4_utils.GLO_message(
                    header=TP4_utils.message_header.OK,
                    data="Le courriel a été envoyé avec succès."
                )
        except smtplib.SMTPException:
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

        Le GLO_message retourné contient dans le champ «data» les entrées:
        - «count», avec le nombre de courriels,
        - «folder_size», avec la taille totale du dossier en octets.
        Si le nom d’utilisateur est invalide, le GLO_message retourné
        indique l’erreur au client.
        """

        # On valide si le user existe
        user_dir_path = os.path.join(self._server_data_path, username)

        if not os.path.isdir(user_dir_path):
            return TP4_utils.GLO_message(
                header=TP4_utils.message_header.ERROR,
                data="L'utilisateur n'existe pas."
            )

        # Compte le nombre de fichiers dans le dossier de l'utilisateur (en excluant le fichier du mot de passe)
        nombre_de_fichier = -1
        for path in os.listdir(user_dir_path):
            nombre_de_fichier += 1

        # Compte la taille du dossier de l'utilisateur
        taille_du_dossier = sum(
            d.stat().st_size for d in os.scandir(user_dir_path) if d.is_file())

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
