# Prose-seat workload test — Oct 18, 2026

Question (Nic, Oct 18): after building muse-glimmer-30b-prose as the
default-chat fallback seat, test it on the workloads default-chat normally
handles (morning-brief, daily-recap, PIE) against the incumbent gemma-4-chat-12b.

## Method

Forge retains no request bodies (requests.db is metadata only), so the three
payloads were reconstructed from real same-day material at the production
shapes measured from the request log:

- morning-brief (caller nexus-daily-briefing; production avg 589 in / 183 out,
  43 s): 362-369 prompt tokens as tokenized, budget 600, temp 0.7.
- daily-recap (nexus-daily-recap; production avg 3,295 in / 556 out, 132 s):
  1,785-1,959 prompt tokens as tokenized (undershoots the 3.3k production
  average), budget 1,200, temp 0.7.
- PIE gate judge (nexus-pie-llm-judge-shadow; production avg 5,222 in / 136
  out, 36 s): 832-838 prompt tokens (undershoots the 5.2k average; the
  candidate-judging task itself is faithful, including candidates drawn from
  real open loops and Nic's stated holds), budget 400, temp 0.

Gemma legs ran through Forge default-chat (production path, streamed, the
production call shape). Prose legs ran direct to Crucible llama-swap port 8099
(the server Forge proxies), plus a final through-Forge pass by model ID after
forge PR #145 deployed. All outputs read foreground from the raw result files
(prose-test-results.json, prose-test2-results.json, prose-test3-results.json,
pie-low-2000.json in this directory). Gemma's walls include production
queueing: requests.db showed 1,817 gemma calls in the test hour at 61.1 s
average and 608 s max. That load is reported, not normalized away.

## Headline result

At production-shaped budgets the prose seat returns NO usable answer on all
three workloads, because Glimmer's reasoning block consumes the entire
completion budget before the visible answer starts. With headroom, or with a
"Reasoning strength: low" system-prompt line, the answers it produces are at
parity with gemma's on quality and factual fidelity. The seat is sound outage
insurance only for callers whose prompts carry the reasoning control or whose
budgets clear the think tax. That is a harness-design requirement, recorded
below per workload.

## Run 1 — production budgets

| Workload | Gemma (Forge) | Prose (direct) |
|---|---|---|
| brief @600 | 147.6 s, stop, 213 out — complete, faithful brief | 21.1 s, length, 600 out, 0 content chars |
| recap @1200 | 276.3 s, length, 1,200 out — faithful but cut mid-sentence (budget below this payload's need; production avg output is 556 on shorter inputs) | 42.7 s, length, 1,200 out, 0 content chars |
| pie @400 | 49.0 s, stop, 310 out — all 8 verdicts, judgment aligned with Nic's holds on ~7 of 8 (small key-capitalization schema drift) | 14.1 s, length, 400 out, 0 content chars |

Diagnosis, verified by a raw streamed probe of the brief payload @900:
897 reasoning_content deltas (4,030 chars of thinking), zero content deltas,
think block never closed. Direct llama.cpp streams separate reasoning into
reasoning_content; through Forge the think text arrives inline as content, so
a Forge fallback consumer at a naive budget receives raw unfinished thinking
as its "answer," which is worse than empty.

## Run 2 — raised budgets and reasoning control (prose, direct)

| Run | Wall | Finish | Completion | Reasoning | Visible answer |
|---|---|---|---|---|---|
| brief @3000 | 52.6 s | stop | 1,370 tok | 5,105 chars (~1,280 tok) | 933 chars (~240 tok) |
| brief @600 + "Reasoning strength: low" | 20.3 s | stop | 503 tok | 1,064 chars (~270 tok) | 1,011 chars (~250 tok) |
| recap @4000 | 139.5 s | stop | 3,876 tok | 9,402 chars (~2,350 tok) | 6,786 chars (~1,700 tok) |
| pie @2500 (default reasoning) | 101.3 s | length | 2,500 tok | 11,560 chars, never closed | 0 |
| pie @1200 + low | 48.8 s | length | 1,200 tok | 4,107 chars (~1,030 tok) | 1,175 chars, cut mid-answer |
| pie @2000 + low | 50.4 s | stop | 1,135 tok | 3,688 chars (~920 tok) | 1,180 chars, all 8 verdicts |

Think tax at default reasoning: roughly 5x the visible answer on the brief,
roughly 1.4x on the recap, and unbounded past 2,500 tokens on the PIE judge.
"Reasoning strength: low" cuts the brief's think by about 5x and the PIE
judge's to ~920 tokens, at no observed quality cost.

## Run 3 — through Forge (forge PR #145 deployed, seat cold)

| Run | Wall | Result |
|---|---|---|
| brief @600, cold seat, via Forge model ID | 26.8 s | finish length; 2,542 chars of inline think, no final answer. The hop (Forge model entry, crucible-prose backend, llama-swap) works end to end; the budget finding reproduces through it. Cold load is inside this wall. |
| brief @600 + low, via Forge | 21.6 s | finish stop, 547 tokens; full answer present after the (short) think block. |

The fallback firing itself (gemma actually failing) was not manufactured in
production; it is unit-covered on the planning chat's side and the model-ID
hop is live-fired here.

## Quality read (foreground, outputs in the result files)

- Briefs: all three completing briefs (gemma, prose raised, prose low) are
  faithful to every input fact, correct on dates and holds, and correctly
  omit the weather line the payload marked unavailable. The low-reasoning
  prose brief is the best structured of the three.
- Recap: gemma's is faithful and well structured but truncated by the test
  budget. Prose's raised-budget recap is faithful in the spot-checked head
  and tail (bench numbers, open items all correct) and materially longer
  (~1,700 visible tokens vs gemma's ~550-1,200): in an outage, recap-class
  consumers get a more verbose recap, complete rather than cut.
- PIE: prose low @2000 produced all 8 verdicts in the exact requested schema
  (gemma drifted key capitalization). Judgment: parked items dropped
  correctly across the board; C7 differed (prose: defer to the afternoon
  edition, citing today's load; gemma: surface_now as a material event) —
  prose's call tracks Nic's one-edition rule more literally. Either is
  defensible; neither surfaced a parked item.

## Design consequences (input to WS2 and any fallback consumer)

1. A fallback consumer that sends a gemma-shaped budget gets nothing usable
  from Glimmer. Fallback readiness per caller = budget at least ~2x the
  visible answer need, or the low-reasoning line in its system prompt.
2. The low-reasoning line is the cheapest insurance: it made brief-class and
  PIE-class calls complete inside ~600 and ~2,000 budgets respectively, with
  no measured quality loss on these payloads. Whether Forge should inject it
  on fallback, or callers should carry it themselves, is a WS2 decision.
3. PIE-class structured judgment is the worst case: default reasoning never
  terminated. Do not route judge-shaped workloads to Glimmer without the
  reasoning control.
4. Latency is not the risk: even cold through Forge, the prose seat answered
  (or finished its think) in 21-27 s versus gemma's 49-276 s under the day's
  production load. In a real gemma outage the fallback is faster than the
  incumbent's loaded normal.

## Stanza exposures (adversarial review of PR #145, accepted and documented)

- The prose stanza is in llama-swap's default swap group: its cold load
  sweeps the other ungrouped Crucible residents (internvl3-vl-14b,
  nuextract3-extract-4b, qwen3-0.6b, qwen3-permissive-vl-8b), and any of those
  loading can evict the prose seat in turn, including mid-outage.
- Memory corner: the qwen3-embed-8b Crucible mirror (~13.8 GiB) loading while
  both Glimmer seats are resident sums past the 48 GiB UMA GPU budget and can
  fail allocation (the newcomer fails; residents are not at risk).
- Both are inherent to the approved on-demand design. Fixes (grouping every
  Crucible stanza, or a persistent prose seat) cost more than the risk while
  prose is a cold fallback. Revisit if the Workstream C eval promotes prose
  to a hotter role.
