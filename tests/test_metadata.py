import hashlib
import pathlib
import unittest as ut

from torrent import metadata


info0_file_content = b'hello, world!\n'
info0_piece_len = 4
info0_file_expect = metadata.MetadataFile(pathlib.Path('abc.txt'), len(info0_file_content), hashlib.md5(info0_file_content).digest())
info0_expect = metadata.MetadataInfo(
    pieces=b''.join(hashlib.sha1(info0_file_content[i:i+info0_piece_len]).digest()
                    for i in range(0, len(info0_file_content), info0_piece_len)),
    pieces_length=info0_piece_len,
    private=1,
    name=pathlib.Path(),
    files=[info0_file_expect],
    total_size=info0_file_expect.length
)

info1_file0_content = b'Hey yo!\n test string and blah blah blah\n'
info1_file0_expect = metadata.MetadataFile(pathlib.Path('def.txt'), len(info1_file0_content))
info1_file1_content = b'Hey yo2!\n lah blah blah'
info1_file1_expect = metadata.MetadataFile(pathlib.Path('def/ghi.txt'), len(info1_file1_content), hashlib.md5(info1_file1_content).digest())
info1_piece_len = 8
info1_expect = metadata.MetadataInfo(
    pieces=b''.join(hashlib.sha1(f[i:i+info1_piece_len]).digest()
                    for f in (info1_file0_content, info1_file1_content)
                    for i in range(0, len(f), info1_piece_len)),
    pieces_length=info1_piece_len,
    private=0,
    name=pathlib.Path('abc'),
    files=[
        info1_file0_expect,
        info1_file1_expect,
    ],
    total_size=info1_file0_expect.length + info1_file1_expect.length,
)

info = (
    {
        b'pieces': info0_expect.pieces,
        b'piece length': info0_expect.pieces_length,
        b'private': info0_expect.private,
        b'name': info0_file_expect.path.as_posix().encode(),
        b'length': info0_file_expect.length,
        b'md5sum': info0_file_expect.md5sum,
    },
    {
        b'pieces': info1_expect.pieces,
        b'piece length': info1_expect.pieces_length,
        b'name': info0_file_expect.path.as_posix().encode(),
        b'files': [
            {
                b'path': list(s.encode() for s in info1_expect.files[0].path.parts),
                b'length': info1_expect.files[0].length,
            },
            {
                b'path': list(s.encode() for s in info1_expect.files[1].path.parts),
                b'length': info1_expect.files[1].length,
                b'md5sum': info1_expect.files[1].md5sum,
            }
        ]
    },
)


class TestMetadata(ut.TestCase):
    # TODO
    pass


class TestMetadataInfo(ut.TestCase):
    # TODO
    def test_raw_data(self):
        for i in info:
            z = metadata.MetadataInfo.from_rawdata(i, 'utf8')


class TestMetadataFile(ut.TestCase):
    # TODO
    pass
