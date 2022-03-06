import pathlib

from torrent import bencode, metadata


class TorrentFile:
    def __init__(self, data: metadata.TorrentMetadata):
        self.metadata = data

    @property
    def info_hash(self):
        return self.metadata.info.info_hash

    @property
    def total_size(self):
        return self.metadata.info.total_size

    @classmethod
    def from_file(cls, fname: pathlib.Path):
        data = metadata.TorrentMetadata(bencode.decode_from_file(fname))
        return cls(data)
