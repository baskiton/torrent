import pathlib

from torrent import bencode, metadata


class Torrent:
    def __init__(self, data: metadata.TorrentMetadata):
        self.metadata = data

        self.uploaded = 0
        self.downloaded = 0
        self.left = data.info.total_size

    @property
    def info_hash(self):
        return self.metadata.info.info_hash

    @classmethod
    def from_file(cls, fname: pathlib.Path):
        data = metadata.TorrentMetadata(bencode.decode_from_file(fname))
        return cls(data)
