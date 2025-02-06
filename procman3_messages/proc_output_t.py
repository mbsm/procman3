"""LCM type definitions
This file automatically generated by lcm.
DO NOT MODIFY BY HAND!!!!
"""

try:
    import cStringIO.StringIO as BytesIO
except ImportError:
    from io import BytesIO
import struct

class proc_output_t(object):
    __slots__ = ["timestamp", "name", "deputy", "group", "stdout"]

    __typenames__ = ["int64_t", "string", "string", "string", "string"]

    __dimensions__ = [None, None, None, None, None]

    def __init__(self):
        self.timestamp = 0
        self.name = ""
        self.deputy = ""
        self.group = ""
        self.stdout = ""

    def encode(self):
        buf = BytesIO()
        buf.write(proc_output_t._get_packed_fingerprint())
        self._encode_one(buf)
        return buf.getvalue()

    def _encode_one(self, buf):
        buf.write(struct.pack(">q", self.timestamp))
        __name_encoded = self.name.encode('utf-8')
        buf.write(struct.pack('>I', len(__name_encoded)+1))
        buf.write(__name_encoded)
        buf.write(b"\0")
        __deputy_encoded = self.deputy.encode('utf-8')
        buf.write(struct.pack('>I', len(__deputy_encoded)+1))
        buf.write(__deputy_encoded)
        buf.write(b"\0")
        __group_encoded = self.group.encode('utf-8')
        buf.write(struct.pack('>I', len(__group_encoded)+1))
        buf.write(__group_encoded)
        buf.write(b"\0")
        __stdout_encoded = self.stdout.encode('utf-8')
        buf.write(struct.pack('>I', len(__stdout_encoded)+1))
        buf.write(__stdout_encoded)
        buf.write(b"\0")

    def decode(data):
        if hasattr(data, 'read'):
            buf = data
        else:
            buf = BytesIO(data)
        if buf.read(8) != proc_output_t._get_packed_fingerprint():
            raise ValueError("Decode error")
        return proc_output_t._decode_one(buf)
    decode = staticmethod(decode)

    def _decode_one(buf):
        self = proc_output_t()
        self.timestamp = struct.unpack(">q", buf.read(8))[0]
        __name_len = struct.unpack('>I', buf.read(4))[0]
        self.name = buf.read(__name_len)[:-1].decode('utf-8', 'replace')
        __deputy_len = struct.unpack('>I', buf.read(4))[0]
        self.deputy = buf.read(__deputy_len)[:-1].decode('utf-8', 'replace')
        __group_len = struct.unpack('>I', buf.read(4))[0]
        self.group = buf.read(__group_len)[:-1].decode('utf-8', 'replace')
        __stdout_len = struct.unpack('>I', buf.read(4))[0]
        self.stdout = buf.read(__stdout_len)[:-1].decode('utf-8', 'replace')
        return self
    _decode_one = staticmethod(_decode_one)

    def _get_hash_recursive(parents):
        if proc_output_t in parents: return 0
        tmphash = (0xdfb26ed59c54aa6b) & 0xffffffffffffffff
        tmphash  = (((tmphash<<1)&0xffffffffffffffff) + (tmphash>>63)) & 0xffffffffffffffff
        return tmphash
    _get_hash_recursive = staticmethod(_get_hash_recursive)
    _packed_fingerprint = None

    def _get_packed_fingerprint():
        if proc_output_t._packed_fingerprint is None:
            proc_output_t._packed_fingerprint = struct.pack(">Q", proc_output_t._get_hash_recursive([]))
        return proc_output_t._packed_fingerprint
    _get_packed_fingerprint = staticmethod(_get_packed_fingerprint)

    def get_hash(self):
        """Get the LCM hash of the struct"""
        return struct.unpack(">Q", proc_output_t._get_packed_fingerprint())[0]

