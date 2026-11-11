# SyntraVariga QNX Build Guard

**AhaWissenschaft · SyntraVariga** — a small, dependency-free host tool for checking QNX cross-build evidence before delivery.

An AArch64 command declaration and an x86-64 deliverable are individually readable, yet mutually inconsistent. This tool compares an explicit delivery target with QNX `qcc`/`q++` target declarations and a supplied ELF's class, byte order, machine and interpreter evidence. It never executes the commands or the artifact.

**Version 0.1.0, engineering prototype. Not affiliated with or endorsed by QNX, BlackBerry, or Devpost.**

## Run in under a minute

Python 3.12.14 on Linux is the tested environment. No third-party dependencies. Native Windows and QNX runtime support are not tested.

```sh
python3 examples/make_demo.py
python3 qnxguard.py examples/compile_commands.json --target aarch64le --elf examples/structural-aarch64.elf
```

The report is `CONSISTENT_IN_SCOPE`, **not** a verified QNX build. The fixtures are generated ELF headers and interpreter strings, not functioning executables, SDK output, or evidence of runtime compatibility.

Now deliberately supply the wrong architecture:

```sh
python3 qnxguard.py examples/compile_commands.json --target aarch64le --elf examples/structural-x86_64.elf
```

The report changes to `CONFLICT`, including `ELF_MACHINE_MISMATCH`, with exit code 1. Input hashes distinguish the compared artifacts.

For a genuine Linux-produced negative input, compile **only the included owned example**, then inspect it without running the binary:

```sh
c++ examples/native_negative.cpp -o examples/native-negative.elf
python3 qnxguard.py examples/compile_commands.json --target x86_64 --elf examples/native-negative.elf
```

On the tested x86-64 Linux host this reports the conflicting AArch64 command declaration and the Linux interpreter. It demonstrates rejection of a real host artifact, not successful QNX compilation. Requires a local C++ compiler; not required for normal use.

## Use on your own inputs

```sh
python3 qnxguard.py /path/to/compile_commands.json --target x86_64 --elf /path/to/app --output report.json
```

Only these explicit input paths are opened. Source paths, working directories, environment variables and `@response` files named in the compilation database are not followed. The report omits source filenames, original commands, macros and unknown interpreter pathnames. No network access is performed. Inputs and report outputs must be regular files. The final path component may not be a symlink. The Linux-tested file guard opens with O_NONBLOCK/O_NOFOLLOW and verifies the opened descriptor with fstat, so a path-only stat check cannot be raced into reading a FIFO. Intermediate directory symlinks are not prohibited. This does not provide a universal timeout for arbitrary filesystems or an OS sandbox; inspect only files you are authorized to read. Existing reports are replaced after the type check; report writes are not crash-atomic.

| Exit | Status | Meaning |
|---|---|---|
| 0 | `CONSISTENT_IN_SCOPE` | Supported declarations and inspected ELF fields agree within this narrow scope. |
| 1 | `CONFLICT` | At least one architecture or recognized non-QNX-loader contradiction. |
| 2 | `INCOMPLETE` or input error | Missing/unsupported evidence, malformed input or report-write error. Input errors use a redacted stderr message. |

**All statuses retain `qnx_os_version: NOT_PROVEN` and `provenance: NOT_VERIFIED`.** A command can be fabricated; a QNX loader pathname can be embedded in any bytes. This tool does not prove that an ELF came from its accompanying commands. It does not guarantee ABI/linkability, function, safety, timing, authenticity, or QNX 8 compatibility. SHA-256 identifies the supplied bytes only.

## Supported evidence

- Explicit `qcc`/`q++` invocations: `-Vgcc_ntoaarch64le`, `-V gcc_ntox86_64`, optional compiler/version prefix and documented `_cxx` / `_gpp` suffixes.
- ELF64 little-endian, `EM_AARCH64` (183) and `EM_X86_64` (62).
- QNX loader paths `/usr/lib/ldqnx-64.so.2` and `/usr/lib/ldqnx-64.so` as pathname evidence only; selected known Linux loader paths as contradictions.
- Missing `PT_INTERP` stays incomplete: objects, static binaries and shared libraries need not contain one.
- Missing `-V` stays incomplete: this tool does not inspect the local QNX SDK's defaults.
- Response files, wrappers, multiple selectors and shell control/expansion syntax stay incomplete. `arguments` arrays are preferred. `command` uses a conservative POSIX parser, not a Windows shell parser.
- 1 MiB / 10,000-entry compilation database, 16 MiB ELF, at most 1,024 program headers. Extended tables are unsupported. This is not a complete compiler-driver or ELF validator.

## Verify

```sh
python3 -m unittest discover -s tests -v
```

Initial release: 33 test methods passed locally on Linux / Python 3.12.14. On 2026-11-10, the regular-file fix at code commit `3be3f570dec2612503f932964d00a10fa12c53ff` passed 39 methods on Linux 6.18.57 / Python 3.12.14. Six added tests reproduce input/output FIFO waits, final-symlink reads/overwrites, and regular-report replacement. Five of six failed against the original code (including three bounded FIFO timeouts); all six pass after the fix. See `evidence/REGULAR_FILE_REVIEW.md`. Tests include parser ambiguity, malformed/truncated ELF, wrong-architecture and Linux-loader negative controls, a harmless shell canary that must not be created, and report redaction. Independent agent review found option-operand, selector-grammar and shell-newline problems; reproducing tests failed before the fixes and passed afterwards. This is local evidence, not an external certification.

## QNX connection and competition status

This host tool's QNX-specific function is relating documented QNX compiler selectors to architecture and loader evidence intended for a QNX delivery. It is not merely a renamed generic linter. It complements tools such as `file` / `readelf` by comparing declarations against an explicit expected target and reporting uncertainty rather than inferring the OS version.

Submitted to the **QNX Global Hackathon, Developer Tooling & Host Tools** category on 2026-11-10 (submission 1293889); Devpost confirmed receipt. This is not a judging acceptance, award or payment. [Entry](https://devpost.com/software/syntravariga-qnx-build-guard). [Demo](https://youtu.be/1i6dZqn9dU0), unlisted at the owner's request. An authentic QNX SDP-produced artifact has not yet been validated. Judge eligibility remains the organizer's decision. See [SUBMISSION.md](SUBMISSION.md) for exact remaining submission items and rules.

## Primary references

- [QNX SDP 8.0 qcc/q++ selectors](https://qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/q/qcc.html)
- [QNX cross-development](https://qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.prog/topic/devel_SELFORCROSS.html)
- [QNX official hello-world artifact example](https://qnx.software/en/blog/2026/qnxe-ftbu-3)
- [QNX dynamic linking](https://qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.sys_arch/topic/dll.html)
- [ELF header](https://gabi.xinuos.com/v42/elf/02-eheader.html), [machine registry](https://gabi.xinuos.com/v42/elf/a-emachine.html), [dynamic linking / PT_INTERP](https://gabi.xinuos.com/elf/09-dynamic.html)
- [Clang compilation database format](https://clang.llvm.org/docs/JSONCompilationDatabase.html)

## License and attribution

MIT. Keep the license and copyright notice in copies or substantial portions, as required by the license. The source, CLI/version output and report carry **SyntraVariga / AhaWissenschaft** attribution. Brand references do not imply endorsement by QNX or permission to impersonate AhaWissenschaft.
