import hashlib
import hmac
import struct
import unittest
from weather_vm import protocol as p

KEY=bytes(range(32));DEVICE=bytes.fromhex('0102030405060708');BOOT=bytes.fromhex('1020304050607080')

class Protocol(unittest.TestCase):
    def test_exact_frozen_sample_wire(self):
        fields=bytes.fromhex('535758310101005001020304050607081020304050607080000000016acf11c00a8c00b60300000044454d4f30303031')
        # Independent big-endian fixture and standard-library HMAC.
        self.assertEqual(len(fields),48)
        self.assertEqual(p.sample(KEY,DEVICE,BOOT,1,1791955392,2700,182,3),
                         fields+hmac.digest(KEY,b'SHINO-WX/SAMPLE/1'+fields,'sha256'))

if __name__=='__main__':unittest.main()
