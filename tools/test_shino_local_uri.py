"""Local package paths: regression for Windows WinError 123 /C:/ bug."""
import unittest
from pathlib import PureWindowsPath, PurePosixPath
from shino_local_framework import platformio_local_uri

class PlatformIOLocalURI(unittest.TestCase):
    def test_windows_drive(self):
        path=PureWindowsPath(r"C:\Users\jerry\SHINO-TV-V06-AUDIT\research-local\candidate\isolated-shino-framework")
        uri=platformio_local_uri(path)
        self.assertEqual(uri,"file://C:/Users/jerry/SHINO-TV-V06-AUDIT/research-local/candidate/isolated-shino-framework")
        # PlatformIO 6.1.18 does uri[7:] and shutil.copytree(source,...)
        self.assertEqual(uri[7:],path.as_posix())
        self.assertNotIn("/C:/",uri[7:])

    def test_posix_absolute(self):
        path=PurePosixPath("/tmp/shino/candidate/isolated-shino-framework")
        uri=platformio_local_uri(path)
        self.assertEqual(uri,"file:///tmp/shino/candidate/isolated-shino-framework")
        self.assertEqual(uri[7:],str(path))

if __name__=="__main__":
    unittest.main()
