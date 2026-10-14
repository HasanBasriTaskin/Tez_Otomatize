import io
import struct
import unittest
from literature.protocol import read_frame, write_frame, validate_message, ProtocolError


class ProtocolTest(unittest.TestCase):
    def test_turkish_roundtrip(self):
        out=io.BytesIO()
        msg={'v':1,'id':'abc','type':'status','payload':{'text':'Türkçe'}}
        write_frame(out,msg)
        out.seek(0)
        self.assertEqual(read_frame(out),msg)

    def test_oversized_truncated_and_invalid_commands(self):
        for data in [struct.pack('<I',300000),struct.pack('<I',10)+b'{}']:
            with self.assertRaises(ProtocolError):
                read_frame(io.BytesIO(data))
        for kind in ['shell','write_file','run','../../file']:
            with self.assertRaises(ProtocolError):
                validate_message({'v':1,'id':'x','type':kind,'payload':{}})

    def test_eof_and_invalid_json(self):
        self.assertIsNone(read_frame(io.BytesIO()))
        with self.assertRaises(ProtocolError):
            read_frame(io.BytesIO(struct.pack('<I',2)+b'!!'))


if __name__=='__main__':unittest.main()
