import hashlib


class Peer:
    def __init__(self, ip, port: int, peer_id: bytes = None):
        self.ip = ip
        self.port = port
        self.peer_id = peer_id
        self.status = None
        self.id = int.from_bytes(hashlib.sha256((self.ip, self.port)).digest(),
                                 'big', signed=False)
