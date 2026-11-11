# Competition submission — receipt confirmed, judging pending

Title: **SyntraVariga QNX Build Guard — declared target vs. delivery artifact**

Brand: **SyntraVariga / AhaWissenschaft**

Category: Developer Tooling & Host Tools

## Short description

A local Python host tool that checks QNX compiler target declarations against the declared delivery architecture and a supplied ELF artifact. It flags conflicting CPU architectures and known Linux-loader evidence, treats missing evidence conservatively, and creates a deterministic redacted JSON report without executing build commands or target code.

## Problem

In cross-development, a valid host executable or wrong-CPU artifact can be handed over alongside plausible QNX build metadata. A generic ELF architecture label alone does not establish QNX provenance. A compiler command alone is only a declaration. This project makes the narrow relationship inspectable and states what remains unproven.

## Demonstration plan — under 3 minutes

1. Show SyntraVariga / AhaWissenschaft branding and the two supported target families.
2. Run the included structural-fixture generator; state explicitly that it creates test headers, not real QNX executables.
3. Run the matching case: CONSISTENT_IN_SCOPE, but QNX version NOT_PROVEN.
4. Swap to the wrong-CPU fixture: CONFLICT / ELF_MACHINE_MISMATCH.
5. Inspect the included example compiled by a native Linux C++ compiler: a real negative control, not a QNX build.
6. Show local tests and the no-execution / no-provenance / no-runtime-guarantee boundaries.

## Actual entry status and remaining validation

Submission 1293889 was confirmed by Devpost on November 10, 2026, 16:11:14 UTC (17:11:14 Europe/Berlin). [Project page](https://devpost.com/software/syntravariga-qnx-build-guard). No judging acceptance, award or payment is claimed.

Demo: https://youtu.be/1i6dZqn9dU0 — 84-second silent replay of actual captured host-tool output, with synthetic positives explicitly labelled. The owner requires unlisted visibility. The live entry form permits public or unlisted video; the official rules say publicly visible. Organizer acceptance of unlisted visibility is not independently confirmed; do not change visibility without owner authorization.

The regular-file fix is included in this public source snapshot; review evidence and tests are included.

Authentic QNX SDP output remains an engineering validation gap. Do not claim compilation or execution on QNX8. No proprietary SDK material is redistributed.

Official rules: https://qnx.devpost.com/rules . Host tools are expressly allowed, but meaningful QNX8 functionality must be demonstrable; final eligibility belongs to the organizer. Deadline: December15,2026,14:00Eastern (20:00Europe/Berlin). Prize outcomes are uncertain; no payment guaranteed.

## AI assistance and prior work

Developed with AI coding and review assistance during November2026. This standalone tool is newly authored. No private SyntraVariga engine code, user credentials or unpublished internal concepts are included. Official technical documentation informed the supported selectors and ELF field interpretation; original documentation prose and SDK binaries are not copied into the project.
