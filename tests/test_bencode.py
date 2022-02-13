import random
import unittest as ut

from torrent import bencode


class TestBencode(ut.TestCase):
    def test_int(self):
        for i in range(-10000, 10000):
            self.assertEqual(i, bencode.decode_from_buffer(f'i{i}e'.encode()), msg=i)

    def test_int_fail(self):
        for i in range(-10000, 10000):
            with self.assertRaises(EOFError, msg=i):
                bencode.decode_from_buffer(f'i{i}'.encode())

    def test_bytes(self):
        for i in range(1000):
            j = random.randint(0, 1000)
            s = random.randbytes(j)
            y = b'%i:%s' % (j, s)
            z = bencode.decode_from_buffer(y)
            self.assertEqual(s, z, msg=y)

    def test_bytes_fail_eof(self):
        for i in range(1000):
            j = random.randint(0, 1000)
            with self.assertRaises(EOFError, msg=j):
                bencode.decode_from_buffer(str(j).encode())

    def test_bytes_fail_val(self):
        for i in range(1000):
            j = random.randint(1, 1000)
            s = random.randbytes(j).replace(b':', b'\0')
            y = b'%i%s' % (j, s)
            with self.assertRaises(ValueError, msg=y):
                bencode.decode_from_buffer(y)

    def test_bytes_fail_key(self):
        x = b':' + b'ololo'
        with self.assertRaises(KeyError, msg=x):
            bencode.decode_from_buffer(x)

    def test_list(self):
        xy = {
            b'l4:spam4:eggse': [b'spam', b'eggs'],
            b'le': [],
        }
        for x, y in xy.items():
            z = bencode.decode_from_buffer(x)
            self.assertListEqual(z, y, msg=f'{x} <-> z')

    def test_dict(self):
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

    def test_dict_fail(self):
        x = b'di12ei21ee'
        with self.assertRaises(TypeError, msg=x):
            bencode.decode_from_buffer(x)

    def test_decode(self):
        x = b'd3:food3:bari-42e6:foobar6:foobar4:listl4:spami42eee6:foobar6:foobar4:zeroi0ee'
        y = {b'foo': {b'bar': -42, b'foobar': b'foobar', b'list': [b'spam', 42]}, b'foobar': b'foobar', b'zero': 0}

        z = bencode.decode_from_buffer(x)

        self.assertDictEqual(z, y, msg=z)

    def test_decode_file(self):
        fn = 'tests/files/SimCity 4 Deluxe Edition [GOG] [RUS ENG MULTI7] [rutracker-5305145].torrent'
        z = bencode.decode_from_file(fn)
        self.assertTrue(z, fn)
