# Final pre-publication pass — privacy and sensitivity review

Scope: the article text and every file in this repository, reviewed
before either is made public (October 24, 2026). This document
supersedes an earlier assembly audit; it is written to describe
categories of findings without reproducing any sensitive value.

## What was scanned

- Pattern scans over all text files for: credential material (API key
  and token formats, key/secret/password assignments, private-key
  blocks), email addresses, phone numbers, IPv4/IPv6 addresses, home
  directory paths, internal work-item IDs, UUIDs, and personal-name
  markers (the author, family members, friends, colleagues, and
  professional contacts).
- Manual read of every payload, prompt, and result file whose content
  is prose rather than measurements, plus the environment manifests.
- Image metadata check on all PNGs (charts and the vision test image).

## Findings and dispositions

**Credentials and secrets: none.** No API keys, tokens, passwords, or
private keys anywhere in the package. One harness script reads an API
key from an environment variable by name, with an empty default; no
value is present.

**Contact and account identifiers: none.** No email addresses, no
phone numbers, no account IDs in tracked file contents. (Git commit
author/committer metadata is a separate surface; see the open
publication decision in `CORRECTIONS.md`.)

**Withheld — personal workload content.** The October 18 prose tests
used private personal and third-party material. The payload files and
the result files generated from them are excluded from this repo; the
records document their shapes, sizes, and results. See the README's
"What's withheld, and why."

**Substituted — third-party names in test prompts.** The agent-suite
prompts in the window 2 and 3 data and harness scripts used four real
contacts' names as `search_contacts` inputs. In the public copies
they are replaced with generic placeholder names (29 substitutions
across 5 files). No measurement depends on the name strings.

**Redacted — one network detail.** A private interconnect address
appeared once in the window 1 record; it is removed in the public
copy. Loopback addresses (127.0.0.1) in server configuration data are
retained; they describe local serving, which is the article's
subject.

**Withheld — operational snapshots.** The llama-swap `/running`
captures contain full production command lines (ports, model roster,
file layout). They evidence window restores only; the records
document the restores, so the snapshots are excluded.

**Reviewed and kept, deliberately:**
- The author's own username in absolute file paths (83 occurrences):
  the repo is published under his own name, and the paths are
  provenance for the raw data.
- The two machine names used throughout the article and records.
- Internal work-item IDs referenced in the records' narrative: bare
  identifiers with no content attached.
- The author's own platform and project names appearing in records
  and harness descriptions: they are his public projects and part of
  the serving story.
- Image metadata: the charts carry only a plotting-library software
  string; the vision test image carries none. The vision image is
  synthetic (drawn shapes), and its ground truth and the model's full
  response are in the window 3 data, as the article states.

**False positives discharged:** numeric strings resembling IP
addresses in server-log excerpts are log timestamps; a four-digit
number resembling a birth year in the power data is a Unix timestamp
fragment and a clock reading.

## Verification

After the changes above, the full pattern scan was re-run over the
repository and the article: no credential material, no email or phone
patterns, no private-network addresses other than loopback, and none
of the personal-name markers remain. The article itself contains no
addresses, identifiers, or personal names beyond the author's own
machine and project names.

The publication copy of the article in this repo (`article/ARTICLE.md`)
differs from the approved draft in exactly three mechanical ways: the
internal draft banner was removed, the chart image paths were adjusted
to this repo's layout (`article/`), and the file was renamed from
ARTICLE-DRAFT.md. No sentence of the body was changed in this pass;
everything else in this document refers to the package as scanned.
A post-review corrections pass followed on 2026-10-24; see
`CORRECTIONS.md`.
