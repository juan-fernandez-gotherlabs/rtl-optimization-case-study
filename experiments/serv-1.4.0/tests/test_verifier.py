"""Reject misleading claims and altered evidence even after checksum rewriting."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('serv_verifier', PACKAGE / 'verify.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class EvidenceTamperingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'case'
        shutil.copytree(PACKAGE, self.root, ignore=shutil.ignore_patterns('__pycache__'))
        self.old_root = verifier.ROOT
        verifier.ROOT = self.root

    def tearDown(self):
        verifier.ROOT = self.old_root
        self.temp.cleanup()

    def reject_rehashed_change(self):
        verifier.write_manifest()
        with self.assertRaises(verifier.VerificationError):
            verifier.main([])

    def test_claiming_completed_final_pairs_is_rejected(self):
        p = self.root / 'results/development.json'
        data = json.loads(p.read_text())
        data.update(certified=True, final_pairs_completed=64, publication_accepted=True)
        p.write_text(json.dumps(data))
        self.reject_rehashed_change()

    def test_rewritten_power_report_is_rejected(self):
        p = self.root / 'evidence/ppa/optimized/5001/serv_synth_wrapper.power'
        p.write_text(p.read_text().replace('0.003352', '0.002352'))
        self.reject_rehashed_change()

    def test_missing_timing_report_is_rejected(self):
        (self.root / 'evidence/ppa/optimized/5012/vpr.crit_path.out').unlink()
        self.reject_rehashed_change()

    def test_changed_rtl_is_rejected(self):
        p = self.root / 'rtl/optimized/serv_alu.v'
        p.write_text(p.read_text() + '\nwire unexpected_wire;\n')
        self.reject_rehashed_change()

    def test_fabricated_formal_closure_is_rejected(self):
        p = self.root / 'evidence/mapped-formal/optimized/formal.log'
        p.write_text('307 are proven and 0 are unproven\nEquivalence successfully proven!\n')
        self.reject_rehashed_change()


if __name__ == '__main__':
    unittest.main()
