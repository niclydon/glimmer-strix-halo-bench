# Glimmer reasoning control: verdict and shipped fix, October 18, 2026

## Probe (Crucible scratch instance, b11719, full offload, production payload shapes)

| control | brief @600 (temp 0.7) | PIE @400 (temp 0) |
|---|---|---|
| --reasoning-budget 0 | length, 2,528 reasoning chars, 0 content | length, 1,881 reasoning, 0 content |
| --reasoning-budget 256 | length, 2,527 reasoning, 0 content | length, 1,881 reasoning, 0 content |
| --reasoning-effort low | stop, 1,362 reasoning, 1,056 content | length, 1,854 reasoning, 0 content |
| --chat-template-kwargs {"reasoning_strength":"low"} | stop, 670 reasoning, 1,083 content | length, 1,854 reasoning, 0 content |

--reasoning off (PR #509) was already proven inert by its post-deploy acceptance. The sampler budget keys on think tags Glimmer does not emit (it reasons in the ATEM channel), so budget values are ignored. The template kwarg is the one working server-side control, and only for prose shapes; judge shapes at 400 tokens are not rescued by any knob. The per-caller rule (max_tokens at least ~2x visible need, or the prompt-carried reasoning line) remains load-bearing for small-budget structured callers.

## Shipped

- homelab PR #514 (merge 88c557c): kwargs flag added to the muse-glimmer-30b-prose stanza.
- homelab PR #515 (merge 9f77f83): quoting fix. As first generated, the bare JSON's double quotes were stripped by llama-swap's shell lexing of the cmd string, llama-server received {reasoning_strength:low} and exited rc=1 in ~3 s. A/B on the host proved it (bare form dead in 3 s, single-quoted form healthy). The manifest flag now carries the JSON single-quoted.
- Acceptance (live, post-#515): prose brief @600 through llama-swap: wall 22.5 s, finish stop, 647 reasoning chars, 1,060 content chars, faithful brief text; the live prose cmdline carries both --chat-template-kwargs and --reasoning off. Agent seat re-verified through Forge (served by muse-glimmer-30b, finish tool_calls, get_backlog_item). Both seats resident and ready.

## Incident notes from the same night

- The #514 deploy left the prose seat down (upstream exiting) until #515; the acceptance caught it before any organic fallback call depended on it.
- The A/B diagnostic's form-B scratch server (port 5998) survived its terminate and held ~20 GB, which blocked the agent seat's reload after the #515 restart with allocation failures ("upstream command exited prematurely") until it was found in the process list and killed. Lesson: scratch servers get a pgrep sweep in the same step that starts them, every time.
- The budget probe's original partial-offload shape (-ngl 16) is implicated in the evening's Crucible wedge: the previous boot's kernel log shows the amdgpu KFD userptr restore worker hogging CPU with counts doubling (21:47Z, 22:46Z, 00:30Z) while sshd stalled pre-auth from every path. The probe was relaunched full-offload (-ngl 99, the production shape) and completed cleanly. Do not run partial-offload Glimmer instances on Crucible again.
