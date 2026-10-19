"""HOST source lineage proof: #83 -> exact #54 M2 -> exact B5.2."""
from pathlib import Path
import unittest
from link_83_source_identity import (
    LINK83_BLOBS, reviewed_m2_source, verify_added_blob,
)
from link_m2_source_identity import (
    LINK_M2_FILE_BLOBS, LINK_PATH, git_blob_sha1,
    reviewed_link_predecessor, LINK_B52_PREDECESSOR_BLOB,
    LinkSourceIdentityError,
)
ROOT=Path(__file__).resolve().parents[1]

class Issue83SourceIdentity(unittest.TestCase):
    def test_every_new_source_is_pinned_and_restores_reviewed_m2(self):
        for path, sha in LINK83_BLOBS.items():
            with self.subTest(path=path):
                bits=(ROOT/path).read_bytes()
                self.assertEqual(git_blob_sha1(bits),sha)
                self.assertTrue(verify_added_blob(bits,path))
                if path in LINK_M2_FILE_BLOBS:
                    old=reviewed_m2_source(bits,path)
                    self.assertEqual(git_blob_sha1(old),LINK_M2_FILE_BLOBS[path])
                    if path==LINK_PATH:
                        self.assertEqual(git_blob_sha1(reviewed_link_predecessor(old)),
                                         LINK_B52_PREDECESSOR_BLOB)

    def test_mutations_are_refused(self):
        for path in LINK83_BLOBS:
            current=(ROOT/path).read_bytes()
            with self.subTest(path=path):
                for candidate in (current+b"\\n#tampered", b"",current[:-1]):
                    with self.assertRaises(LinkSourceIdentityError):
                        verify_added_blob(candidate,path)
                    if path in LINK_M2_FILE_BLOBS:
                        with self.assertRaises(LinkSourceIdentityError):
                            reviewed_m2_source(candidate,path)

if __name__=="__main__":
    unittest.main()
