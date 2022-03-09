import struct
import unittest as ut
import urllib.parse

from btorrent.transport import peer as transport


class TestTransportTracker(ut.TestCase):
    def test_http_request(self):
        u = urllib.parse.urlparse('http://aaa.b/announce')
        params = {}

        self.assertTrue(0)

    def test_udp_request(self):
        u = urllib.parse.urlparse('udp://aaa.b/announce')

        self.assertTrue(0)


class TestTransportPeer(ut.TestCase):
    def test_utp(self):
        self.assertTrue(0)

    def test_messages(self):
        # Handshake
        _hdsh_ver = 1
        _hdsh_rsrv = 0xBADC0FFEE0DDF00D
        _hdsh_ihash = b'info hash test value'
        _hdsh_pid = b':peer id test value:'
        _msg_bin = struct.pack(f'!B{len(transport.PROTOCOL_NAME_v10)}sQ20s20s',
                               len(transport.PROTOCOL_NAME_v10), transport.PROTOCOL_NAME_v10,
                               _hdsh_rsrv, _hdsh_ihash, _hdsh_pid)

        _msg = transport.Handshake(_hdsh_rsrv, _hdsh_ihash, _hdsh_pid, _hdsh_ver)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.Handshake)
        self.assertEqual(_hdsh_rsrv, _msg.reserved)
        self.assertEqual(_hdsh_ihash, _msg.info_hash)
        self.assertEqual(_hdsh_pid, _msg.peer_id)

        # Keep alive
        _msg = transport.KeepAlive()
        _msg_bin = struct.pack('!I', _msg.BASE_LENGTH)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.KeepAlive)
        self.assertEqual(0, _msg.length_prefix)

        # Choke
        _msg = transport.Choke()
        _msg_bin = struct.pack('!IB', _msg.BASE_LENGTH, _msg.MESSAGE_ID)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.Choke)

        # UnChoke
        _msg = transport.UnChoke()
        _msg_bin = struct.pack('!IB', _msg.BASE_LENGTH, _msg.MESSAGE_ID)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.UnChoke)

        # Interested
        _msg = transport.Interested()
        _msg_bin = struct.pack('!IB', _msg.BASE_LENGTH, _msg.MESSAGE_ID)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.Interested)

        # NotInterested
        _msg = transport.NotInterested()
        _msg_bin = struct.pack('!IB', _msg.BASE_LENGTH, _msg.MESSAGE_ID)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.NotInterested)

        # Have
        _pidx = 1234
        _msg = transport.Have(_pidx)
        _msg_bin = struct.pack('!IBI', _msg.BASE_LENGTH, _msg.MESSAGE_ID, _pidx)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.Have)
        self.assertEqual(_pidx, _msg.piece_index)

        # Bitfield
        _bf = b'bitfiled'
        _msg = transport.Bitfield(_bf)
        _msg_bin = struct.pack(f'!IB{len(_bf)}s', _msg.BASE_LENGTH + len(_bf), _msg.MESSAGE_ID, _bf)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.Bitfield)
        self.assertEqual(_bf, _msg.bitfield)

        # Request
        _idx = 123
        _bg = 456
        _len = 789
        _msg = transport.Request(_idx, _bg, _len)
        _msg_bin = struct.pack('!IB3I', _msg.BASE_LENGTH, _msg.MESSAGE_ID, _idx, _bg, _len)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.Request)
        self.assertEqual(_idx, _msg.index)
        self.assertEqual(_bg, _msg.begin)
        self.assertEqual(_len, _msg.length)

        # Piece
        _idx = 123
        _bg = 456
        _blk = b'block'
        _msg = transport.Piece(_idx, _bg, _blk)
        _msg_bin = struct.pack(f'!IBII{len(_blk)}s', _msg.BASE_LENGTH + len(_blk), _msg.MESSAGE_ID, _idx, _bg, _blk)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.Piece)
        self.assertEqual(_idx, _msg.index)
        self.assertEqual(_bg, _msg.begin)
        self.assertEqual(_blk, _msg.block)

        # Cancel
        _idx = 123
        _bg = 456
        _len = 789
        _msg = transport.Cancel(_idx, _bg, _len)
        _msg_bin = struct.pack('!IB3I', _msg.BASE_LENGTH, _msg.MESSAGE_ID, _idx, _bg, _len)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.Cancel)
        self.assertEqual(_idx, _msg.index)
        self.assertEqual(_bg, _msg.begin)
        self.assertEqual(_len, _msg.length)

        # Port
        _port = 7777
        _msg = transport.Port(_port)
        _msg_bin = struct.pack('!IBH', _msg.BASE_LENGTH, _msg.MESSAGE_ID, _port)
        self.assertEqual(_msg_bin, _msg.to_bytes())

        _msg = transport.Message.from_bytes(_msg_bin)
        self.assertIsInstance(_msg, transport.Port)
        self.assertEqual(_port, _msg.listen_port)
