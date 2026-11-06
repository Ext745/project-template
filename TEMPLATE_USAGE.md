# Using this template

Delete this file from a project once it's set up. (`make prepublish` warns if it's still there.)

Shared policy files (AI policy, approach, contributing, security, support, issue/PR templates) live once in **`Ext745/.github`**, not in each repo, so they can't drift. GitHub applies the community files from there to every repo that doesn't have its own.

## New project
1. On GitHub: **Use this template → Create a new repository**. Private is fine; see "Going public".
2. Clone, then `make setup` (installs the pre-commit hooks: gitleaks + personal-data scrub). Install [gitleaks](https://github.com/gitleaks/gitleaks/releases) locally for `make prepublish`.
3. Fill in `docs/origin.md` with your prior-art research.
4. Write `GOAL.md`. Non-goals and acceptance criteria matter most.
5. Fill in `AGENTS.md` (hazards, conventions) and the `Makefile` targets `build` / `test` / `hil`.
6. Fill in the rig table and maturity criteria in `TESTING.md`.
7. Fill in or delete the regulatory lines in `docs/hardware.md`.
8. Set the year in `LICENSE` (or swap the license; MIT is the default).
9. Start the agent with: *"Read AGENTS.md, GOAL.md and docs/origin.md, then get started."*

## Releases
Tag a release when the project reaches a new maturity level. List the soak runs that back it in `CHANGELOG.md` and attach their `output.log` files to the GitHub release.

## Going public (private → public)
History goes public with the repo. Anything ever committed is exposed, even if it was deleted later.
1. `make prepublish`: checks secrets and personal data in **full history**, forbidden strings from `.prepublish-deny`, large files, LICENSE and README.
2. If history is dirty: rewrite it with `git filter-repo`, or publish a fresh single-commit history. **Rotate any secret that was ever committed.**
3. Flip visibility, then:
   ```bash
   gh repo edit Ext745/<repo> --add-topic ai-assisted,hardware-tested
   gh api -X PUT repos/Ext745/<repo>/private-vulnerability-reporting
   ```

## Auditing everything you already have
Before rolling this out, and periodically after:
```bash
gh auth login                                   # once
python3 tools/audit-all.py                      # every repo on your account, full history
python3 tools/audit-all.py --local ~/workbench/ai_projects --no-github   # local checkouts
```
Read-only: it mirror-clones into `~/.cache/repo-audit/` and writes `audit-<date>.md` there (mode 600, values redacted). Public repos with secrets come first, plus what to do about each finding.

## Retrofitting an existing repo
- [ ] Copy in: `AGENTS.md` + `CLAUDE.md` symlink, `Makefile`, `tools/`, `.pre-commit-config.yaml`, `.gitignore` entries, `.github/workflows/ci.yml`, `TESTING.md`, `STATUS.md`, `CHANGELOG.md`
- [ ] Remove any per-repo copies of policy / issue / PR templates that should come from `Ext745/.github`
- [ ] Add the maturity / tested-on / soak line and the "How this project is built" section to the README
- [ ] Write `GOAL.md` from what the project actually turned out to be
- [ ] Write `STATUS.md`, honestly, including what's untested
- [ ] Backfill `TESTING.md` with hardware runs you've already done. Mark them *backfilled*; approximate durations are fine if you say so.
- [ ] Record the 2–5 most important past decisions in `docs/decisions/`
- [ ] Move abandoned code and experiments into `lab/` with short `NOTES.md` files
- [ ] If it's a fork: state the upstream, what you changed, keep the upstream LICENSE and attribution, and note that upstream isn't responsible for your changes
- [ ] `make setup`, then `make prepublish` before it's (or while it is) public
