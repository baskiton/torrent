import pathlib
import secrets

from torrent import bencode, metadata, __version__


class Torrent:
    def __init__(self, data: metadata.TorrentMetadata):
        self.metadata = data

        # tracker requests keys
        # self.info_hash
        self.peer_id = f'-PB{int(__version__.replace(".", "")[:4]):04}-'.encode() + secrets.token_bytes(12)
        self.port = [*range(6881, 6890)]
        self.uploaded = 0
        self.downloaded = 0
        self.left = data.info.total_size
        self.compact = 0
        # self.ip
        # self.numwant = 50

    @property
    def info_hash(self):
        return self.metadata.info.info_hash

    @classmethod
    def from_file(cls, fname: pathlib.Path):
        data = metadata.TorrentMetadata(bencode.decode_from_file(fname))
        return cls(data)
