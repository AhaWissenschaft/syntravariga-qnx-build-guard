import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest


class FileBoundaryTests(unittest.TestCase):
    def run_guard(self, *args):
        try:
            return subprocess.run([sys.executable, 'qnxguard.py', *map(str, args)],
                                  capture_output=True, text=True, timeout=2)
        except subprocess.TimeoutExpired:
            self.fail('CLI blocked on a non-regular file')

    def assert_rejected(self, result, private_path):
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertIn('input/report error', result.stderr)
        self.assertNotIn(str(private_path), result.stderr)

    def test_database_fifo_is_rejected_without_waiting_for_writer(self):
        with tempfile.TemporaryDirectory() as d:
            fifo = Path(d) / 'private-db'; os.mkfifo(fifo)
            self.assert_rejected(self.run_guard(fifo, '--target', 'x86_64'), fifo)

    def test_elf_fifo_is_rejected_without_waiting_for_writer(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'db'; db.write_text('[]')
            fifo = Path(d) / 'private-elf'; os.mkfifo(fifo)
            self.assert_rejected(self.run_guard(db, '--target', 'x86_64', '--elf', fifo), fifo)

    def test_report_fifo_is_rejected_without_waiting_for_reader(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'db'; db.write_text('[]')
            fifo = Path(d) / 'private-report'; os.mkfifo(fifo)
            self.assert_rejected(self.run_guard(db, '--target', 'x86_64', '--output', fifo), fifo)

    def test_final_input_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d) / 'real'; real.write_text('[]')
            link = Path(d) / 'private-link'; link.symlink_to(real)
            self.assert_rejected(self.run_guard(link, '--target', 'x86_64'), link)

    def test_final_output_symlink_does_not_truncate_target(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'db'; db.write_text('[]')
            real = Path(d) / 'real'; real.write_text('retain this')
            link = Path(d) / 'private-link'; link.symlink_to(real)
            self.assert_rejected(self.run_guard(db, '--target', 'x86_64', '--output', link), link)
            self.assertEqual(real.read_text(), 'retain this')

    def test_regular_report_replaces_old_content_and_is_parseable(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'db'; db.write_text('[]')
            output = Path(d) / 'report'; output.write_text('old' * 10000)
            result = self.run_guard(db, '--target', 'x86_64', '--output', output)
            self.assertEqual(result.returncode, 2)  # valid report, incomplete evidence
            self.assertEqual(result.stderr, '')
            self.assertEqual(json.loads(output.read_text())['status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
