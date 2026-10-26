# Corrections — post-review pass, 2026-10-24

This package was reviewed independently before publication: an
adversarial benchmark review plus a sensitive-information pass over
the private staging repository. The reviewer reproduced the
measurements from the data (all 65 standalone llama-bench rows, the
KV aggregates, the soak totals) and found no fabrication. The
corrections below concern interpretation, provenance statements,
grading labels, and packaging. The article in `article/ARTICLE.md`
is the corrected version. The bench records keep their original text,
with dated interpretation notes added at the top; nothing
contemporaneous was rewritten.

## Article claim corrections

- Window 1 DFlash at depth: relabeled as synthetic prompt-continuation
  throughput. The three runs per cell were three different prompt
  variants; two continue the prompt's own instruction list and only
  one writes the story. The prose-ranking cross-check drawn from that
  sweep and the branch-probability reading are removed; the
  story-variant observations (n=1 per cell) are reported separately.
- Power soak: the two per-request rate clusters are described without
  an acceptance mechanism; the soak retained neither outputs nor
  acceptance counters.
- KV at 131k: the prompt construction and the per-run draft acceptance
  were recorded in the data and are now stated; earlier statements
  that they were not recorded were wrong. Recorded acceptance (f16
  171/1244, 13.7%; q8_0 175/1172, 14.9%) does not explain the decode
  deficit.
- Reasoning tax: the reasoning-to-answer ratio is in characters
  (about 3.6x), not tokens; no token split was measured.
- Cold latency: labeled as single first-cold observations per
  configuration, each followed by a warm-prefix run.
- Tool-call scores: labeled as a signature check (expected function
  name plus one required argument key). Window 2's arguments were
  retained and re-examined in review; window 3's were not retained,
  and its score cannot be regraded. Equal smoke-test scores do not
  establish quality equivalence.
- Serving matrix: configured slots and concurrent requests changed
  together. The claim is restated as no near-linear aggregate scaling
  from one to four active requests, with the 131k aggregate rise
  (15.41 to 19.49 tok/s) stated. Single-active-request speed across
  slot counts was not tested.
- Novelty: prior first-party Glimmer-on-Strix-Halo measurements
  (August 2026) are now cited; the piece is framed as an operational
  case study extending them.

## Data corrections

- `data/w3/llamabench-UD-Q5_K_XL.json` and the consolidated copy in
  `data/w3/results-w3.json`: the stored `stddev_ns` for the depth-0
  tg128 row (3,345,753,631 ns in the original capture) is inconsistent
  with its own samples ([20100486487, 17570304335, 19889302226] ns).
  Corrected here to the sample standard deviation, 1,403,814,549.29
  ns, reconciled against the original capture, which is unchanged.
  The row's mean and all token/s figures were and remain consistent;
  no article number changes.
- The derived `cache_hit_rate` field in `data/w2/results-w2.json`
  (written by `harness/bench_w2.py`) divides cached tokens by
  processed tokens and can exceed 1; it is not a fraction and should
  be ignored. The article's percentages use
  cached/(cached + processed). The raw file is left as captured; this
  note is the correction.
- Soak counts: 6,757 measurement rows in `data/w3/power.csv` plus its
  header; the soak slice is 1,826 rows; the slow cluster extends to
  9.1495 tok/s. Article text corrected.

## Charts

- `article/chart-kv.png`: panels now read "124k filled in 131k ctx".
- `article/chart-hip-vulkan.png`: the ubatch-256 diamond is labeled
  with its depth (32,768) and dispersion (±0.94 tok/s); the depth
  axes note that spacing is not to scale.

## Privacy-pass changes in this pass

- Descriptions of the withheld prose-workload material were
  generalized in `README.md` and `FINAL-PASS.md`; the categories of
  withheld content are not needed to interpret the benchmarks.
- The no-email statement in `FINAL-PASS.md` is scoped to tracked
  file contents.

## Open publication decision

- The commits in this repository's history carry the author's
  personal email in author/committer metadata. Tracked file contents
  contain no email address. Before any public release, the author
  will either accept that disclosure explicitly or publish from a
  sanitized history. It is recorded here so the choice is deliberate.
  The repository remains private in the meantime.

## Second review pass — 2026-10-24

A second independent audit (recomputing every article number from the
raw data) produced further corrections, applied the same day:

- The window 1 HIP decode cliff did not reproduce: window 3 read
  12.21 tok/s in the same nominal cell (HIP, ubatch 512, depth
  32,768) against window 1's 6.43. The article now presents the cliff
  as a one-window observation with unknown cause; the within-window
  ubatch comparison was time-confounded. The chart title and the
  settings-card advice were corrected accordingly.
- Quant ladder: the first-pass Q4 depth-0 figure (9.93 tok/s) is now
  disclosed alongside the supplemental run's 11.65, and the deficit
  range is stated as roughly 26-43% across both passes. The Q5/Q6
  depth-0 separation is described with its actual thinness (intervals
  miss overlapping by 0.03; reps overlap). The agent-suite subset is
  described as the synthetic task set it is.
- Reasoning control: the article now reports the probe table as
  recorded - `--reasoning-budget` inert, `--reasoning-effort low`
  partial (brief completed with content comparable to the kwarg),
  `--reasoning off` proven inert separately - and states that no knob
  rescued judge-shaped calls at small budgets.
- Setup: production serving is from Crucible only; "same build" is
  scoped to one commit in four build trees; the raw /completion
  construction of the server-path benches is stated in the setup; the
  external KV figure is linked to its primary source and marked as
  context this repo cannot check.
- Story-variant ranges at depth are stated across all draft sizes
  (HIP 10.6-16.4, Vulkan 9.7-18.9 tok/s).
- Vision: the response also called the rectangle a square; the
  article now counts three misses.
- Harness: `analyze_w1.py` and `analyze_w2.py` now resolve their data
  paths relative to the script instead of hard-coded absolute paths.
- Records: status lines from the moment of writing are annotated as
  such; the README's withheld list now includes the longtext payload;
  FINAL-PASS's substitution note covers recorded outputs as well as
  prompts, and its path-occurrence count is corrected to 82.

- Operational narrative in the records (sprint references, work-item
  IDs, the production model roster, a host-wedge recipe) was
  considered for trimming in this pass and deliberately left intact:
  the records are contemporaneous evidence, none of it is secret,
  and corrections ride in dated notes rather than rewrites.

## History sanitization (October 26, 2026)

The open publication decision from the first review (finding 14) is
closed: the history was sanitized before any public flip. All six
commits had their author and committer email replaced with the
GitHub noreply address for this account (via git filter-repo) and
the rewritten history was force-pushed while the repo is still
private. File contents are unchanged: the tip tree hash is
identical before and after the rewrite. Commit messages and
tracked contents contained no email address. Future commits in
this repo use the noreply identity (repo-local git config).
