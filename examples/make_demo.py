"""Generate labeled structural fixtures; does NOT compile or run QNX software."""
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent


def main():
    entries = [{'directory': '/example/build', 'file': 'hello.c',
                'arguments': ['qcc', '-Vgcc_ntoaarch64le', '-c', 'hello.c']}]
    (ROOT / 'compile_commands.json').write_text(json.dumps(entries, indent=2) + '\n', encoding='utf-8')
    interpreter = b'/usr/lib/ldqnx-64.so.2\0'
    for name, machine in (('structural-aarch64.elf', 183), ('structural-x86_64.elf', 62)):
        ident = b'\x7fELF' + bytes([2, 1, 1, 0]) + bytes(8)
        header = struct.pack('<HHIQQQIHHHHHH', 3, machine, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
        program = struct.pack('<IIQQQQQQ', 3, 4, 120, 0, 0, len(interpreter), len(interpreter), 1)
        (ROOT / name).write_bytes(ident + header + program + interpreter)
    print('SyntraVariga / AhaWissenschaft: created STRUCTURAL TEST FIXTURES, not executable QNX builds.')


if __name__ == '__main__':
    main()
