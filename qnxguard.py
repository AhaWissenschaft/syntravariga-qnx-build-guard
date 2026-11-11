"""SyntraVariga / AhaWissenschaft — static QNX build evidence inspector.

Never executes compilation commands, opens response files or loads an ELF.
Consistency within this scope does not prove provenance or QNX OS version.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import stat
import struct
import sys

VERSION = '0.1.0'
MAX_DATABASE = 1024 * 1024
MAX_ELF = 16 * 1024 * 1024
TARGETS = {'x86_64': 62, 'aarch64le': 183}
SELECTORS = {f'gcc_nto{arch}{suffix}': arch for arch in TARGETS
             for suffix in ('', '_cxx', '_gpp')}
QNX_LOADERS = {'/usr/lib/ldqnx-64.so.2', '/usr/lib/ldqnx-64.so'}
LINUX_LOADERS = {'/lib/ld-linux-aarch64.so.1', '/lib64/ld-linux-x86-64.so.2',
                 '/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2',
                 '/lib/ld-musl-x86_64.so.1', '/lib/ld-musl-aarch64.so.1'}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key; refusing ambiguous input.')
        result[key] = value
    return result


def _finding(findings, code, severity, location):
    findings.append({'code': code, 'severity': severity, 'location': location})


def _argv(entry):
    """Return literal argument vector or unsupported reason; never evaluate shell."""
    if 'arguments' in entry:
        args = entry['arguments']
        if not isinstance(args, list) or not args or not all(isinstance(a, str) and '\0' not in a for a in args):
            raise ValueError('arguments must be a nonempty array of strings without NUL.')
        return args, None
    command = entry.get('command')
    if not isinstance(command, str) or not command or '\0' in command:
        raise ValueError('Compilation entry needs arguments or a command string.')
    if '\n' in command or '\r' in command:
        return [], 'SHELL_SYNTAX_UNSUPPORTED'
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|<>()')
        lexer.whitespace_split = True
        lexer.commenters = ''
        args = list(lexer)
    except ValueError as exc:
        raise ValueError('Cannot parse command as a POSIX argument string.') from exc
    if not args:
        raise ValueError('Empty compilation command.')
    if any(any(c in a for c in ';&|<>()$`') for a in args):
        return [], 'SHELL_SYNTAX_UNSUPPORTED'
    return args, None


def _declared_target(args):
    name = args[0].replace('\\', '/').rsplit('/', 1)[-1].lower()
    if name not in ('qcc', 'q++', 'qcc.exe', 'q++.exe'):
        return None, 'COMPILER_UNSUPPORTED'
    if any(arg.startswith('@') for arg in args[1:]):
        return None, 'RESPONSE_FILE_NOT_INSPECTED'
    variants = []
    i = 1
    while i < len(args):
        arg = args[i]
        if arg == '--':
            break
        if arg in ('-o', '-D', '-U', '-I', '-L', '-l', '-x', '-Y', '-B',
                   '-include', '-imacros', '-isystem', '-iquote', '-idirafter',
                   '-isysroot', '--sysroot', '-MF', '-MT', '-MQ'):
            i += 1
            if i >= len(args):
                return None, 'OPTION_OPERAND_MISSING'
        elif arg == '-V':
            i += 1
            if i >= len(args):
                return None, 'TARGET_SELECTOR_MISSING_VALUE'
            variants.append(args[i])
        elif arg.startswith('-V'):
            variants.append(arg[2:])
        i += 1
    if not variants:
        return None, 'IMPLICIT_TARGET'
    if len(variants) != 1:
        return None, 'MULTIPLE_TARGET_SELECTORS'
    variant = variants[0]
    parts = variant.split(',')
    if len(parts) > 2 or any(not part for part in parts):
        return None, 'TARGET_SELECTOR_UNSUPPORTED'
    if len(parts) == 2 and not re.fullmatch(r'[A-Za-z0-9_.+-]+(?:/[A-Za-z0-9_.+-]+)*', parts[0]):
        return None, 'TARGET_SELECTOR_UNSUPPORTED'
    selected = SELECTORS.get(parts[-1])
    return (selected, None) if selected else (None, 'TARGET_SELECTOR_UNSUPPORTED')


def _inspect_elf(data, target, findings):
    if len(data) > MAX_ELF:
        raise ValueError('ELF exceeds 16 MiB limit.')
    if len(data) < 16 or data[:4] != b'\x7fELF':
        raise ValueError('Invalid or truncated ELF identification.')
    elf_class, encoding, ident_version = data[4:7]
    if ident_version != 1 or encoding not in (1, 2) or elf_class not in (1, 2):
        raise ValueError('Unsupported ELF identification.')
    result = {'class': elf_class, 'encoding': encoding, 'machine': None,
              'interpreter_evidence': 'NOT_INSPECTED', 'provenance': 'NOT_VERIFIED'}
    if elf_class != 2:
        _finding(findings, 'ELF_CLASS_MISMATCH', 'error', 'elf')
        return result
    if len(data) < 64:
        raise ValueError('Truncated ELF64 header.')
    order = '<' if encoding == 1 else '>'
    fields = struct.unpack_from(order + 'HHIQQQIHHHHHH', data, 16)
    kind, machine, version = fields[:3]
    phoff, ehsize, phsize, phnum = fields[4], fields[7], fields[8], fields[9]
    result.update(machine=machine, type=kind)
    if version != 1 or ehsize != 64:
        raise ValueError('Invalid ELF64 header version or size.')
    if encoding != 1:
        _finding(findings, 'ELF_ENDIAN_MISMATCH', 'error', 'elf')
    if machine != TARGETS[target]:
        _finding(findings, 'ELF_MACHINE_MISMATCH', 'error', 'elf')
    if kind not in (1, 2, 3):
        _finding(findings, 'ELF_TYPE_UNSUPPORTED', 'unknown', 'elf')
    if phnum > 1024:
        raise ValueError('Extended/large ELF program-header tables are unsupported.')
    if phnum and (phsize != 56 or phoff < 64 or phoff + phnum * phsize > len(data)):
        raise ValueError('Invalid or truncated ELF program-header table.')
    interpreter = None
    for i in range(phnum):
        p = struct.unpack_from(order + 'IIQQQQQQ', data, phoff + i * phsize)
        if p[0] != 3:  # PT_INTERP
            continue
        if interpreter is not None:
            raise ValueError('Multiple PT_INTERP segments are ambiguous.')
        offset, size = p[2], p[5]
        if size < 2 or size > 4096 or offset + size > len(data):
            raise ValueError('Invalid ELF interpreter segment bounds.')
        raw = data[offset:offset + size]
        if raw[-1:] != b'\0' or b'\0' in raw[:-1]:
            raise ValueError('ELF interpreter must be one NUL-terminated string.')
        try:
            interpreter = raw[:-1].decode('ascii')
        except UnicodeDecodeError as exc:
            raise ValueError('ELF interpreter pathname is not ASCII.') from exc
    if interpreter in QNX_LOADERS:
        result['interpreter_evidence'] = 'QNX_LOADER_PATH'
    elif interpreter in LINUX_LOADERS:
        result['interpreter_evidence'] = 'LINUX_LOADER_PATH'
        _finding(findings, 'NON_QNX_LOADER', 'error', 'elf')
    else:
        result['interpreter_evidence'] = 'ABSENT' if interpreter is None else 'UNRECOGNIZED'
        _finding(findings, 'INTERPRETER_NOT_PROVEN', 'unknown', 'elf')
    # Path is deliberately not echoed; an untrusted artifact can embed secrets.
    return result


def inspect_build(database, target, elf=None):
    if target not in TARGETS:
        raise ValueError('Target must be x86_64 or aarch64le.')
    if not isinstance(database, bytes) or len(database) > MAX_DATABASE:
        raise ValueError('Compilation database must be bytes, at most 1 MiB.')
    try:
        entries = json.loads(database.decode('utf-8-sig'), object_pairs_hook=_unique_object,
                             parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonstandard JSON number.')))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Compilation database is not valid UTF-8 JSON.') from exc
    if not isinstance(entries, list) or len(entries) > 10000:
        raise ValueError('Compilation database must be an array of at most 10000 entries.')
    findings, declarations = [], []
    if not entries:
        _finding(findings, 'EMPTY_COMPILATION_DATABASE', 'unknown', 'database')
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) and entry[k] for k in ('file', 'directory')):
            raise ValueError('Each entry needs nonempty file and directory strings.')
        args, reason = _argv(entry)
        declared, reason = (None, reason) if reason else _declared_target(args)
        location = f'entries[{index}]'
        declarations.append({'index': index, 'target': declared, 'evidence': 'DECLARED_NOT_EXECUTED'})
        if reason:
            _finding(findings, reason, 'unknown', location)
        elif declared != target:
            _finding(findings, 'TARGET_MISMATCH', 'error', location)
    artifact = None
    if elf is None:
        _finding(findings, 'ELF_NOT_PROVIDED', 'unknown', 'elf')
    elif not isinstance(elf, bytes):
        raise ValueError('ELF input must be bytes.')
    else:
        artifact = _inspect_elf(elf, target, findings)
    status = ('CONFLICT' if any(f['severity'] == 'error' for f in findings) else
              'INCOMPLETE' if findings else 'CONSISTENT_IN_SCOPE')
    return {'schema_version': 1, 'producer': 'SyntraVariga / AhaWissenschaft', 'tool_version': VERSION,
            'status': status, 'expected_target': target, 'qnx_os_version': 'NOT_PROVEN',
            'provenance': 'NOT_VERIFIED', 'entry_count': len(entries), 'declarations': declarations,
            'artifact': artifact, 'findings': findings,
            'input_sha256': {'compilation_database': hashlib.sha256(database).hexdigest(),
                             'elf': hashlib.sha256(elf).hexdigest() if elf is not None else None},
            'limits': ['No compilation or target execution.', 'No QNX OS-version, ABI, linkability, timing or functional guarantee.',
                       'Declared commands are untrusted evidence; no binding between an entry and the supplied ELF is proven.',
                       'SHA-256 identifies input bytes, not correctness or authenticity.',
                       'No source, response-file or dependency paths from the database are opened.']}


def _read_bounded(path, limit):
    fd = _open_regular(path, os.O_RDONLY)
    try:
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
    finally:
        os.close(fd)
    if len(data) > limit:
        raise ValueError('Input exceeds documented size limit.')
    return data


def _open_regular(path, access):
    # Fail closed if these Linux-tested protections are unavailable.
    if not all(hasattr(os, flag) for flag in ('O_NONBLOCK', 'O_NOFOLLOW')):
        raise ValueError('Regular-file guard is unsupported on this platform.')
    fd = os.open(path, access | os.O_NONBLOCK | os.O_NOFOLLOW |
                 getattr(os, 'O_CLOEXEC', 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Only regular files are supported.')
    except BaseException:
        os.close(fd)
        raise
    return fd


def _write_report(path, text):
    fd = _open_regular(path, os.O_WRONLY | os.O_CREAT)
    try:
        # Do not truncate until the opened descriptor passes the type check.
        os.ftruncate(fd, 0)
        with os.fdopen(fd, 'w', encoding='utf-8', closefd=False) as stream:
            stream.write(text)
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', help='Explicit compile_commands.json input; never executed')
    parser.add_argument('--target', choices=tuple(TARGETS), required=True)
    parser.add_argument('--elf', help='Explicit ELF input; read as bytes, never executed')
    parser.add_argument('--output', help='Optional JSON report output path; otherwise stdout')
    parser.add_argument('--version', action='version', version=f'SyntraVariga / AhaWissenschaft QNX Build Guard {VERSION}')
    args = parser.parse_args(argv)
    try:
        result = inspect_build(_read_bounded(args.database, MAX_DATABASE), args.target,
                               _read_bounded(args.elf, MAX_ELF) if args.elf else None)
        text = json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False) + '\n'
        if args.output:
            _write_report(args.output, text)
        else:
            sys.stdout.write(text)
        return {'CONSISTENT_IN_SCOPE': 0, 'CONFLICT': 1, 'INCOMPLETE': 2}[result['status']]
    except (OSError, ValueError, RecursionError) as exc:
        # Fixed redacted message: no source paths, JSON fragments or embedded secrets.
        sys.stderr.write(f'SyntraVariga / AhaWissenschaft: input/report error ({type(exc).__name__}); check the documented format and size limits.\n')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
