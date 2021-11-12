"""\
Module fournissant les fonctions d’envoi et de réception 
de messages de taille arbitraire pour les sockets Python.
"""
import socket
import struct
from typing import *


def _recvall(source: socket.socket, taille: int) -> Union[bytes, None]:
    """ 
    Fonction utilitaire pour recv_msg.

    Applique socket.recv en boucle pour jusqu’à la
    réception d’un message de la taille voulue.
    """
    msg = b""
    while (taille > 0):
        buffer = source.recv(taille)
        if not buffer:
            return None
        msg += buffer
        taille -= len(buffer)
    return msg


def send_msg(destination: socket.socket, message: str) -> None:
    """ 
    Encode le message puis le transmet à la destination.
    """
    donnee = message.encode(encoding='utf-8')
    destination.sendall(struct.pack(">I", len(donnee)))
    destination.sendall(donnee)


def recv_msg(source: socket.socket) -> Optional[str]:
    """ 
    Récupère un message de la source et le décode.

    Retourne None si la source s’est déconnectée.
    """
    donnee = _recvall(source, 4)
    if donnee is not None:
        taille, = struct.unpack(">I", donnee)
    else:
        return None

    donnee = _recvall(source, taille)
    if donnee is not None:
        return donnee.decode('utf-8')
    else:
        return None
