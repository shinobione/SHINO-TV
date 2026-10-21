"""Negative checks of the exact source overlay, synthetic bytes only."""
import unittest
from materialize import apply_exact, patch_sections

class Integrity(unittest.TestCase):
    def test_exact_context(self):
        self.assertEqual(apply_exact(b'a\nb\n','@@ -1,2 +1,2 @@\n a\n-b\n+c\n'),b'a\nc\n')
    def test_modified_context_refused(self):
        with self.assertRaises(ValueError):apply_exact(b'altered\n','@@ -1 +1 @@\n-a\n+b\n')
    def test_wrong_hunk_counts_refused(self):
        with self.assertRaises(ValueError):apply_exact(b'a\n','@@ -1,2 +1 @@\n-a\n+b\n')
    def test_substitution_or_path_escape_refused(self):
        for path in ('../../firmware/main.cpp','host/unknown.h'):
            with self.assertRaises(ValueError):patch_sections('--- a/'+path+'\n+++ b/'+path+'\n@@ -0,0 +1 @@\n+x\n')

if __name__=='__main__':unittest.main(verbosity=2)
