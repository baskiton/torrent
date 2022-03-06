import hashlib
import pathlib
import unittest as ut

from btorrent import metadata


class TestMetadata(ut.TestCase):
    # TODO
    pass


class TestMetadataInfo(ut.TestCase):
    def setUp(self):
        _piece_len = 4

        _file0_content = b'hello, world!\n'
        _file0 = {
            'content': _file0_content,
            'path': pathlib.Path('abc.txt'),
            'length': len(_file0_content),
            'md5sum': hashlib.md5(_file0_content).digest(),
        }
        _file1_content = b'Hey yo!\n test string and blah blah blah\n'
        _file1 = {
            'content': _file1_content,
            'path': pathlib.Path('def.txt'),
            'length': len(_file1_content),
            'md5sum': None,
        }
        _file2_content = b'Hey yo2!\n lah blah blah'
        _file2 = {
            'content': _file2_content,
            'path': pathlib.Path('def/ghi.txt'),
            'length': len(_file2_content),
            'md5sum': hashlib.md5(_file2_content).digest(),
        }
        _info0_pieces = b''.join(hashlib.sha1(_file0_content[i:i+_piece_len]).digest()
                                 for i in range(0, len(_file0_content), _piece_len))
        _info0_hashes = tuple(_info0_pieces[i:i + 20] for i in range(0, len(_info0_pieces), 20))
        _info1_pieces = b''.join(hashlib.sha1(f[i:i+_piece_len]).digest()
                                 for f in (_file1_content, _file2_content)
                                 for i in range(0, len(f), _piece_len))
        _info1_hashes = tuple(_info1_pieces[i:i + 20] for i in range(0, len(_info1_pieces), 20))
        self._expected_info = (
            {
                'pieces': _info0_pieces,
                'piece_length': _piece_len,
                'private': 1,
                'name': pathlib.Path(),
                'files': [_file0],
                'total_size': _file0['length'],
                'hashes': _info0_hashes,
                'pieces_amount': len(_info0_hashes),
            },
            {
                'pieces': _info1_pieces,
                'piece_length': _piece_len,
                'private': 0,
                'name': pathlib.Path('abc'),
                'files': [_file1, _file2],
                'total_size': _file1['length'] + _file2['length'],
                'hashes': _info1_hashes,
                'pieces_amount': len(_info1_hashes),
            },
        )
        self._raw_info = (
            {
                b'pieces': _info0_pieces,
                b'piece length': _piece_len,
                b'private': 1,
                b'name': str(_file0['path']).encode(),
                b'length': _file0['length'],
                b'md5sum': _file0['md5sum'],
            },
            {
                b'pieces': _info1_pieces,
                b'piece length': _piece_len,
                b'name': b'abc',
                b'files': [
                    {
                        b'path': [p.encode() for p in _file1['path'].parts],
                        b'length': _file1['length'],
                    },
                    {
                        b'path': [p.encode() for p in _file2['path'].parts],
                        b'length': _file2['length'],
                        b'md5sum': _file2['md5sum'],
                    },
                ],
            },
        )

    def test_raw_data(self):
        for i in range(len(self._raw_info)):
            raw = self._raw_info[i]
            exp = self._expected_info[i]
            info = metadata.MetadataInfo.from_rawdata(raw, 'utf8')

            self.assertEqual(info.pieces, exp['pieces'])
            self.assertEqual(info.piece_length, exp['piece_length'])
            self.assertEqual(info.private, exp['private'])
            self.assertEqual(info.name, exp['name'])
            self.assertEqual(info.total_size, exp['total_size'])
            self.assertEqual(info.hashes, exp['hashes'])
            self.assertEqual(info.pieces_amount, exp['pieces_amount'])
            files = exp['files']
            for k in range(len(files)):
                self.assertEqual(info.files[k].path, files[k]['path'])
                self.assertEqual(info.files[k].length, files[k]['length'])
                self.assertEqual(info.files[k].md5sum, files[k]['md5sum'])
