import glob
import io
import pathlib
import random
import secrets
import string
import unittest as ut

from torrent import bencode


class TestBencode(ut.TestCase):
    def setUp(self):
        self._decode_int_fixture = (
            -1 << 63,       # min int64_t
            -1000,
            '-001000',
            -1,
            '-001',
            0,
            '000',
            1,
            '001',
            1000,
            '001000',
            (1 << 63) - 1,  # max int64_t
        )

    def test_decode_int(self):
        for i in self._decode_int_fixture:
            self.assertEqual(int(i), bencode.decode_from_buffer(f'i{i}e'.encode('utf8')), msg=i)

    def test_decode_int_fail(self):
        for i in self._decode_int_fixture:
            with self.assertRaises(EOFError, msg=i):
                bencode.decode_from_buffer(f'i{i}'.encode('utf8'))

    def test_decode_buffer(self):
        for i in range(1000):
            j = random.randint(0, 1000)
            s = secrets.token_bytes(j)
            y = b'%i:%s' % (j, s)
            z = bencode.decode_from_buffer(y)
            self.assertEqual(s, z, msg=y)

    def test_decode_buffer_fail_eof(self):
        for i in range(1000):
            j = random.randint(0, 1000)
            with self.assertRaises(EOFError, msg=j):
                bencode.decode_from_buffer(str(j).encode('utf8'))

    def test_decode_buffer_fail_val(self):
        for i in range(1000):
            j = random.randint(1, 1000)
            s = secrets.token_bytes(j).replace(b':', b'\0')
            y = b'%i%s' % (j, s)
            with self.assertRaises((ValueError, EOFError), msg=y):
                bencode.decode_from_buffer(y)

    def test_decode_buffer_fail(self):
        x = b':' + b'ololo'
        with self.assertRaises(ValueError, msg=x):
            bencode.decode_from_buffer(x)

    def test_decode_list(self):
        xy = {
            b'l4:spam4:eggse': [b'spam', b'eggs'],
            b'le': [],
        }
        for x, y in xy.items():
            z = bencode.decode_from_buffer(x)
            self.assertListEqual(z, y, msg=f'{x} <-> z')

    def test_decode_dict(self):
        xy = {
            b'd3:cow3:moo4:spam4:eggse': {b'cow': b'moo', b'spam': b'eggs'},
            b'd4:spaml1:a1:bee': {b'spam': [b'a', b'b']},
            b'd9:publisher3:bob17:publisher-webpage15:www.example.com18:publisher.location4:homee':
                {b'publisher': b'bob', b'publisher-webpage': b'www.example.com', b'publisher.location': b'home'},
            b'de': {},
            b'd3:food3:bard6:foobari0eeee': {b'foo': {b'bar': {b'foobar': 0}}}
        }
        for x, y in xy.items():
            z = bencode.decode_from_buffer(x)
            self.assertDictEqual(z, y, msg=f'{x} <-> {z}')

    def test_decode_dict_fail(self):
        x = b'di12ei21ee'
        with self.assertRaises(TypeError, msg=x):
            bencode.decode_from_buffer(x)

    def test_decode(self):
        x = b'd3:food3:bari-42e6:foobar6:foobar4:listl4:spami42eee6:foobar6:foobar4:zeroi0ee'
        y = {b'foo': {b'bar': -42, b'foobar': b'foobar', b'list': [b'spam', 42]}, b'foobar': b'foobar', b'zero': 0}

        z = bencode.decode_from_buffer(x)

        self.assertDictEqual(z, y, msg=z)

    def test_decode_fail(self):
        with self.assertRaises(ValueError):
            bencode.decode_from_buffer(b'hello world')

    def test_decode_file(self):
        for p in glob.iglob('tests/files/*.torrent'):
            fn = pathlib.Path(p)
            z = bencode.decode_from_file(fn)
            self.assertTrue(z, msg=f'"{fn}"')

    def test_encode_int(self):
        x = (
            (-6846533, b'i-6846533e'),
            (-1000, b'i-1000e'),
            (-1, b'i-1e'),
            (0, b'i0e'),
            (1, b'i1e'),
            (1000, b'i1000e'),
            (486664324548, b'i486664324548e'),
        )
        for a, exp in x:
            to = io.BytesIO()
            bencode._encode_int(a, to)
            self.assertEqual(exp, to.getvalue(), msg=f'"{a}"')

    def test_encode_buffer(self):
        x = (
            ('hello', b'5:hello'),
            (string.printable, f'{len(string.printable.encode("utf8"))}:{string.printable}'.encode('utf8')),
            ('кириллица', f'{len("кириллица".encode("utf8"))}:кириллица'.encode('utf8')),
            ('кириллица & ascii', f'{len("кириллица & ascii".encode("utf8"))}:кириллица & ascii'.encode('utf8')),
            (b'byte string', b'11:byte string'),
            (b''.join(i.to_bytes(1, 'little', signed=False) for i in range(256)),
             b'256:' + b''.join(i.to_bytes(1, 'little', signed=False) for i in range(256))),
        )
        for a, exp in x:
            to = io.BytesIO()
            bencode._encode_buffer(a, to)
            self.assertEqual(exp, to.getvalue(), msg=f'"{a}"')

    def test_encode_buffer_fail(self):
        self.assertRaises(TypeError, bencode._encode_buffer, 111, io.BytesIO())
        self.assertRaises(TypeError, bencode._encode_buffer, [222], io.BytesIO())
        self.assertRaises(TypeError, bencode._encode_buffer, {'111': 333}, io.BytesIO())

    def test_encode_list(self):
        x = (
            ([], b'le'),
            ([[]], b'llee'),
            ([[], ()], b'llelee'),
            ([([()],)], b'lllleeee'),
            ([1, (2, [3, (4,)])], b'li1eli2eli3eli4eeeee'),
            ([([(1,), 2], 3), 4], b'lllli1eei2eei3eei4ee'),
            (['ололо'], f'l{len("ололо".encode("utf8"))}:ололоe'.encode('utf8')),
            (['helloe'], b'l6:helloee'),
            ([{'key': 'val'}, 3], b'ld3:key3:valei3ee'),
        )
        for a, exp in x:
            to = io.BytesIO()
            bencode._encode_list(a, to)
            self.assertEqual(exp, to.getvalue(), msg=f'"{a}"')

    def test_encode_dict_ok(self):
        x = (
            ({'let': 'b'}, b'd3:let1:be'),
            ({'dig': -123}, b'd3:digi-123ee'),
            ({'dict': {'list': []}}, b'd4:dictd4:listleee'),
            ({'dict': {'dict': {'dict': {'dict': dict()}}}}, b'd4:dictd4:dictd4:dictd4:dictdeeeee'),
            ({'a': 1, 'c': 3, 'e': 5, 'd': 4, 'b': 2}, b'd1:ai1e1:bi2e1:ci3e1:di4e1:ei5ee'),
        )
        for a, exp in x:
            to = io.BytesIO()
            bencode._encode_dict(a, to)
            self.assertEqual(exp, to.getvalue(), msg=f'"{a}"')

    def test_encode_dict_fail(self):
        self.assertRaises(TypeError, bencode._encode_dict, {111: 111}, io.BytesIO())
        self.assertRaises(TypeError, bencode._encode_dict, {(): 222}, io.BytesIO())

    def test_encode_ok(self):
        a = {'dict': [1, b'\0']}
        exp = b'd4:dictli1e1:\0ee'
        out = bencode.encode(a)
        self.assertEqual(exp, out.getvalue(), msg=f'"{a}"')

    def test_encode_fail(self):
        self.assertRaises(TypeError, bencode.encode, 1.2)
