import io
import unittest
from literature.ipc import Peer
from literature.protocol import read_frame


class PeerTest(unittest.TestCase):
    def test_oversized_reply_returns_bounded_error(self):
        output=io.BytesIO()
        peer=Peer(output,lambda *args:{'text':'x'*300000},lambda peer:None)
        peer.capacity.acquire()
        try:
            peer._dispatch({'v':1,'id':'large','type':'status','payload':{}})
            output.seek(0);reply=read_frame(output)
            self.assertIsNotNone(reply)
            self.assertFalse(reply['ok'])
            self.assertEqual(reply['id'],'large')
        finally:peer.pool.shutdown()


if __name__=='__main__':unittest.main()
