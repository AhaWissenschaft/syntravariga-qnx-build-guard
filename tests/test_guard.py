import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from qnxguard import inspect_build


def database(*args, command=None):
    row = {'directory': '/never-followed', 'file': 'not-executed.c'}
    if command is not None:
        row['command'] = command
    else:
        row['arguments'] = list(args or ('qcc', '-Vgcc_ntoaarch64le', '-c', 'not-executed.c'))
    return json.dumps([row]).encode()


def elf_fixture(machine=183, interpreter='/usr/lib/ldqnx-64.so.2', endian=1, kind=3):
    """Structural test fixture, NOT a compiled QNX executable."""
    order = '<' if endian == 1 else '>'
    ident = b'\x7fELF' + bytes([2, endian, 1, 0]) + bytes(8)
    payload = interpreter.encode() + b'\0' if interpreter is not None else b''
    header = struct.pack(order + 'HHIQQQIHHHHHH', kind, machine, 1, 0,
                         64 if payload else 0, 0, 0, 64, 56 if payload else 0,
                         1 if payload else 0, 0, 0, 0)
    ph = struct.pack(order + 'IIQQQQQQ', 3, 4, 120, 0, 0, len(payload), len(payload), 1) if payload else b''
    return ident + header + ph + payload


class GuardTests(unittest.TestCase):
    def test_aarch64_qcc_declaration_conflicts_with_x86_delivery(self):
        database = json.dumps([{
            'directory': '/not-read', 'file': 'hello.c',
            'arguments': ['qcc', '-Vgcc_ntoaarch64le', '-c', 'hello.c'],
        }]).encode()
        report = inspect_build(database, 'x86_64')
        self.assertEqual(report['status'], 'CONFLICT')
        self.assertIn('TARGET_MISMATCH', [f['code'] for f in report['findings']])

    def test_matching_declared_target_and_structural_elf(self):
        r = inspect_build(database(), 'aarch64le', elf_fixture())
        self.assertEqual(r['status'], 'CONSISTENT_IN_SCOPE')
        self.assertEqual(r['qnx_os_version'], 'NOT_PROVEN')
        self.assertEqual(r['artifact']['interpreter_evidence'], 'QNX_LOADER_PATH')

    def test_x86_target_and_realistic_version_selector(self):
        r = inspect_build(database('q++', '-Vgcc/12.0,gcc_ntox86_64_cxx', 'x.cc'), 'x86_64', elf_fixture(62))
        self.assertEqual(r['status'], 'CONSISTENT_IN_SCOPE')

    def test_separated_v_selector(self):
        r = inspect_build(database('/opt/qnx/host/qcc', '-V', '12.0,gcc_ntoaarch64le_gpp', 'x.c'), 'aarch64le', elf_fixture())
        self.assertEqual(r['status'], 'CONSISTENT_IN_SCOPE')

    def test_unversioned_documented_qnx_loader_is_evidence(self):
        r = inspect_build(database(), 'aarch64le', elf_fixture(interpreter='/usr/lib/ldqnx-64.so'))
        self.assertEqual(r['status'], 'CONSISTENT_IN_SCOPE')

    def test_no_elf_is_incomplete_not_verified(self):
        self.assertEqual(inspect_build(database(), 'aarch64le')['status'], 'INCOMPLETE')

    def test_implicit_qcc_defaults_not_assumed(self):
        r = inspect_build(database('qcc', 'x.c'), 'x86_64', elf_fixture(62))
        self.assertEqual(r['status'], 'INCOMPLETE')
        self.assertIn('IMPLICIT_TARGET', [f['code'] for f in r['findings']])

    def test_response_file_not_followed_or_assumed(self):
        r = inspect_build(database('qcc', '-Vgcc_ntoaarch64le', '@secrets.txt'), 'aarch64le', elf_fixture())
        self.assertEqual(r['status'], 'INCOMPLETE')

    def test_non_qnx_compiler_not_claimed_qnx(self):
        r = inspect_build(database('gcc', '-D__QNX__', 'x.c'), 'aarch64le', elf_fixture())
        self.assertEqual(r['status'], 'INCOMPLETE')

    def test_conflicting_multiple_v_options_not_silently_accepted(self):
        r = inspect_build(database('qcc', '-Vgcc_ntoaarch64le', '-Vgcc_ntox86_64', 'x.c'), 'x86_64', elf_fixture(62))
        self.assertEqual(r['status'], 'INCOMPLETE')

    def test_unknown_target_not_misclassified(self):
        r = inspect_build(database('qcc', '-Vgcc_ntoarmv7le', 'x.c'), 'aarch64le', elf_fixture())
        self.assertEqual(r['status'], 'INCOMPLETE')

    def test_empty_database_cannot_vacuously_pass(self):
        self.assertEqual(inspect_build(b'[]', 'aarch64le', elf_fixture())['status'], 'INCOMPLETE')

    def test_json_duplicate_keys_rejected(self):
        with self.assertRaises(ValueError):
            inspect_build(b'[{"file":"a","file":"b","directory":"/"}]', 'aarch64le')

    def test_malformed_json_and_schema_rejected(self):
        for raw in (b'{}', b'[null]', b'[] trailing', b'[{"arguments":"qcc"}]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                inspect_build(raw, 'aarch64le')

    def test_cpu_mismatch_detected(self):
        r = inspect_build(database(), 'aarch64le', elf_fixture(62))
        self.assertEqual(r['status'], 'CONFLICT')
        self.assertIn('ELF_MACHINE_MISMATCH', [f['code'] for f in r['findings']])

    def test_linux_loader_not_mistaken_for_qnx(self):
        r = inspect_build(database(), 'aarch64le', elf_fixture(interpreter='/lib/ld-linux-aarch64.so.1'))
        self.assertEqual(r['status'], 'CONFLICT')
        self.assertIn('NON_QNX_LOADER', [f['code'] for f in r['findings']])

    def test_unknown_loader_does_not_imply_linux_or_qnx(self):
        r = inspect_build(database(), 'aarch64le', elf_fixture(interpreter='/private/custom/loader'))
        self.assertEqual(r['status'], 'INCOMPLETE')

    def test_absence_of_interp_is_unknown_not_automatic_failure(self):
        r = inspect_build(database(), 'aarch64le', elf_fixture(interpreter=None, kind=1))
        self.assertEqual(r['status'], 'INCOMPLETE')
        self.assertNotIn('NON_QNX_LOADER', [f['code'] for f in r['findings']])

    def test_big_endian_artifact_conflicts_with_supported_little_endian_targets(self):
        r = inspect_build(database(), 'aarch64le', elf_fixture(endian=2))
        self.assertEqual(r['status'], 'CONFLICT')

    def test_32bit_artifact_conflicts_with_supported_64bit_targets(self):
        raw = bytearray(elf_fixture()); raw[4] = 1
        self.assertEqual(inspect_build(database(), 'aarch64le', bytes(raw))['status'], 'CONFLICT')

    def test_truncated_and_bad_magic_artifacts_rejected(self):
        for raw in (b'bad', b'\x7fELF' + bytes(12), elf_fixture()[:100]):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                inspect_build(database(), 'aarch64le', raw)

    def test_interpreter_offset_bounds_checked(self):
        raw = bytearray(elf_fixture()); struct.pack_into('<Q', raw, 72, 999999)
        with self.assertRaises(ValueError):
            inspect_build(database(), 'aarch64le', bytes(raw))

    def test_nul_terminated_interpreter_required(self):
        raw = bytearray(elf_fixture()); raw[-1] = 65
        with self.assertRaises(ValueError):
            inspect_build(database(), 'aarch64le', bytes(raw))

    def test_source_paths_and_commands_not_disclosed(self):
        raw = json.dumps([{'directory':'/private/secret','file':'private-key.c','arguments':['qcc','-Vgcc_ntoaarch64le','-DSECRET=abc123','private-key.c']}]).encode()
        output = json.dumps(inspect_build(raw, 'aarch64le', elf_fixture()))
        for secret in ('/private/secret', 'private-key.c', 'abc123'):
            self.assertNotIn(secret, output)

    def test_command_form_parsed_without_execution(self):
        r = inspect_build(database(command='qcc -Vgcc_ntoaarch64le -c "a b.c"'), 'aarch64le', elf_fixture())
        self.assertEqual(r['status'], 'CONSISTENT_IN_SCOPE')

    def test_shell_control_command_is_incomplete_and_never_executed(self):
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d) / 'canary'
            r = inspect_build(database(command=f'qcc -Vgcc_ntoaarch64le x.c; touch {marker}'), 'aarch64le', elf_fixture())
            self.assertFalse(marker.exists())
            self.assertEqual(r['status'], 'INCOMPLETE')

    def test_input_size_bounded(self):
        with self.assertRaises(ValueError):
            inspect_build(b' ' * (1024 * 1024 + 1), 'aarch64le')

    def test_same_inputs_produce_deterministic_report(self):
        self.assertEqual(inspect_build(database(), 'aarch64le', elf_fixture()), inspect_build(database(), 'aarch64le', elf_fixture()))

    def test_cli_exit_and_branding(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'db.json'; p.write_bytes(database())
            r = subprocess.run([sys.executable, 'qnxguard.py', str(p), '--target', 'x86_64'], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            report = json.loads(r.stdout)
            self.assertEqual(report['status'], 'CONFLICT')
            self.assertIn('SyntraVariga', report['producer'])
            self.assertIn('AhaWissenschaft', report['producer'])

    def test_option_operands_are_not_target_options(self):
        for option in ('-o', '-D', '-I', '-include', '-isystem', '-L', '-U', '-x', '-Y'):
            with self.subTest(option=option):
                r = inspect_build(database('qcc', option, '-Vgcc_ntoaarch64le', 'x.c'), 'aarch64le', elf_fixture())
                self.assertEqual(r['status'], 'INCOMPLETE')

    def test_malformed_v_prefix_does_not_prove_a_target(self):
        for selector in ('-Vjunk,extra,gcc_ntoaarch64le', '-V,gcc_ntoaarch64le', '-Vbad prefix,gcc_ntoaarch64le'):
            with self.subTest(selector=selector):
                r = inspect_build(database('qcc', selector, 'x.c'), 'aarch64le', elf_fixture())
                self.assertEqual(r['status'], 'INCOMPLETE')

    def test_shell_newline_not_merged_into_one_command(self):
        r = inspect_build(database(command='qcc -Vgcc_ntoaarch64le -c x.c\nfalse'), 'aarch64le', elf_fixture())
        self.assertEqual(r['status'], 'INCOMPLETE')

    def test_end_of_options_stops_selector_interpretation(self):
        r = inspect_build(database('qcc', '--', '-Vgcc_ntoaarch64le'), 'aarch64le', elf_fixture())
        self.assertEqual(r['status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
