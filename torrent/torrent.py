import pathlib

from torrent import bencode, metadata


class Torrent:
    def __init__(self, data: metadata.TorrentMetadata):
        self.metadata = data

    @classmethod
    def from_file(cls, fname: pathlib.Path):
        data = metadata.TorrentMetadata(bencode.decode_from_file(fname))
        return cls(data)
