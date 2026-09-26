import hashlib
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from inspect_factory import inspect, parse_esp8266_image, printable_strings


class FirmwareInspectionTests(unittest.TestCase):
    def test_recognizes_esp8266_segment(self):
        body = b'firmware test /api.json hello\0'
        data = bytes((0xe9, 1, 2, 0x40)) + struct.pack('<I', 0x40100000)
        data += struct.pack('<II', 0x3ffe8000, len(body)) + body + b'\x00\xef'
        parsed = parse_esp8266_image(data)
        self.assertTrue(parsed['recognized'])
        self.assertEqual(parsed['segment_count'], 1)
        self.assertEqual(parsed['flash_mode'], 'DIO')
        self.assertEqual(parsed['segments'][0]['size'], len(body))
        self.assertEqual(parsed['payload_bytes_after_segments'], 2)

    def test_rejects_invalid_and_truncated_images(self):
        self.assertFalse(parse_esp8266_image(b'invalid')['recognized'])
        image = bytes((0xe9, 1, 2, 0x40)) + struct.pack('<I', 123)
        self.assertFalse(parse_esp8266_image(image)['recognized'])
        self.assertFalse(parse_esp8266_image(image + struct.pack('<II', 0x1000, 10) + b'abc')['recognized'])

    def test_reads_zip_and_digests(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'factory.zip'
            bin_data = b'not a flash image'
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
                z.writestr('firmware.bin', bin_data)
                z.writestr('md5sum.txt', hashlib.md5(bin_data).hexdigest())
            result = inspect(path)
            self.assertEqual(len(result['firmwares']), 1)
            self.assertEqual(result['firmwares'][0]['sha256'], hashlib.sha256(bin_data).hexdigest())
            self.assertFalse(result['firmwares'][0]['header']['recognized'])
            self.assertEqual(len(result['vendor_md5_text']), 1)

    def test_collects_candidate_route_strings(self):
        self.assertEqual(printable_strings(b'abc /rotation.json xyz', 10)[0]['offset'], '0x0')


if __name__ == '__main__':
    unittest.main()
