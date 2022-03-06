import hashlib


class Peer:
    def __init__(self, ip, port: int, peer_id: bytes = None):
        self.ip = ip
        self.port = port
        self.peer_id = peer_id
        self.status = None
        self.id = hashlib.sha256(str((self.ip, self.port)).encode()).digest()

    def __eq__(self, other: 'Peer'):
        return self.id == other.id

    def __repr__(self):
        return f'Peer({self.ip}:{self.port})'
