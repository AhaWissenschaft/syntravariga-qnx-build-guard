# Regular-file boundary review — 2026-11-10

Base public commit: 25cc876fdba3cb2f0378c363ce3df01bd27c2b4c
Fixed code commit (local isolated branch): 3be3f570dec2612503f932964d00a10fa12c53ff
Host: Linux6.18.57 / Python3.12.14. No Windows or QNX runtime test.

Baseline: python3 -m unittest discover -s tests -v -> exit0,33 methods.
Regression-before-fix: python3 -m unittest discover -s tests -p test_file_io.py -v -> exit1,6 methods,5 failures. Three are two-second timeouts opening database/ELF/report FIFOs without a peer. Two show unwanted final-symlink following/truncation. Ordinary report replacement already passes.
After fix: python3 -m unittest discover -s tests -v -> exit0,39 methods.

Fix: O_NONBLOCK/O_NOFOLLOW opening plus fstat of actual descriptor; reject nonregular files; verify type before truncating output; close descriptors in all paths. Missing platform flags fail closed. No universal arbitrary-filesystem deadline or crash-atomic report guarantee; intermediate directory symlinks are allowed.

These are owned test fixtures. No customer code or target executable executed. Tests launch the owned host Python CLI only. Synthetic positive ELF fixtures remain synthetic; no genuine QNX SDK binary validation claimed.

Publication: this fix is NOT on public main. Native Git push dry-run failed because no terminal GitHub credential was available. No credentials requested, no merge/force push/Actions. Standard connector public commit route remains blocked by previous personal author/email metadata issue. Store candidate privately, publish only through a verified branded/noreply identity route. Existing public commit history is not corrected.

Submission: Devpost confirmation email1a1c63a6d62a2096 independently read; subject Submission confirmed: SyntraVariga QNX Build Guard, date2026-11-10T16:11:14Z. DKIM/SPF/DMARC pass recorded by Gmail. This proves entry receipt, not judging eligibility, certification, prize or payment.

Official QNX qcc selector reference, dynamic-linking page and From The Board Up3 article opened successfully. The article documents /usr/lib/ldqnx-64.so.2 output; it is documentation evidence, not possession/testing of that artifact. No downloadable binary found on that inspected article.

Automation: Builder enabled/hourly. Latest recorded run failed despite containing a positive report/receipt; controller paused. Runtime cause unproven. No schedules or enable flags changed. Do not promise unattended successful operation or earnings.
