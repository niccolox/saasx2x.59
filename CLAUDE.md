# CLAUDE.md

SaaSX2X is an uptime and site reliability monitor. [PRODUCT.md](PRODUCT.md) records the product decisions. [docs/design/slice-1/](docs/design/slice-1/) records the design of the first slice. `SYNTHESIS.md` in that folder is the design contract.

The bet record is `.local/research/bet-process.md`. The `bet-record` skill in `.claude/skills/bet-record/` reads and checks it.

## Use pstack from backnotprop/pstack only

- Use the pstack skills in `.claude/skills/`. [skills-lock.json](skills-lock.json) pins them to one commit of `backnotprop/pstack`.
- Start each task with `/poteto-mode`.
- Do not use or recommend `BhaskarManam/pstack`. It is a different project with the same name.

## Do not use gstack

- Do not use, start, or recommend a gstack skill in this project.
- `skillOverrides` in [.claude/settings.json](.claude/settings.json) turns off each gstack skill. If a gstack upgrade adds a skill, add its name to that list with the value `"off"`.
- The gstack hooks in `~/.claude/settings.json` exit at once when the session folder is in this project.

## Read the pstack model settings from this project

The pstack model settings are in [.claude/rules/pstack-models.md](.claude/rules/pstack-models.md), not in `~/.claude/rules/pstack-models.md`. When a pstack skill names the user path, read the project file instead. Use its role lines for every subagent model choice.

Claude Code subagents have no fast mode, and Gemini is not available here. A `-fast` slug runs at standard speed with the same effort level.
