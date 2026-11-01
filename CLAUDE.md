# folded-veil: portfolio project

A folded aluminium veil over an 18 x 12 m facade: parametric geometry, field, fabrication families, nesting, IFC model and sun-hours study, in plain Python with tests. Portfolio piece for Walid's computational design work; project page on archicoder.com.

@README.md

## Rules
- Every number in the README and on the project page is measured from the coordinates. Change a claim only after re-running the code that proves it.
- After any change in `src/`, run `python tests/test_veil.py` (and `python tests/test_bim.py` for IFC work).
- Rhino and Grasshopper files (`rhino/`, `grasshopper/`) are made on Walid's PC. Do not regenerate them in a cloud session.
- Requirements are split: `requirements-bim.txt`, `requirements-sun-inputs.txt`, `requirements-video.txt`. Install only what the task needs.

## Working with Walid
- Reply in Arabic unless he writes in English. Short and practical: what changed, how to check it.
- He often works from his phone (Claude Code on the web). Keep summaries short enough for a phone screen.
- Never use the long dash (—) in anything you write: copy, docs, commit messages, replies. Use a period, colon, comma or parentheses.
- Ask before adding a dependency or changing a business rule.

## Git and secrets
- Commit and push directly to `main` (Walid's choice, Nov 2026, for every repo). No branches or PRs unless he asks.
- Before pushing: the build passes and the tests near your change pass. Run `git pull --rebase` first.
- Never commit secrets (`.env`, `.dev.vars`, API keys). Secrets live in the Cloudflare dashboard.
- Do not deploy (wrangler deploy, pages deploy) unless Walid asks in this session.
