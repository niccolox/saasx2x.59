# pstack model configuration. One line per role. Delete a line to fall back to the skill default.
# `inherit-parent` or `auto` as a value: the role runs on the parent chat model (omit the subagent `model`). Alias entries in a panel list still count toward its fan-out.
# defaults: 2
# budget: large (xhigh)
feature, refactoring: claude-opus-5-5-xhigh
bug-fix: claude-opus-5-5-xhigh
perf-issue: claude-opus-5-5-xhigh
hillclimb: claude-opus-5-5-xhigh
judgment and prose: claude-opus-5-5-xhigh
hardest tasks: claude-fable-5-2-max
reflect tooling: claude-opus-5-5-high
reflect judgment, divergent, synthesizer: claude-opus-5-5-xhigh
arena runners: claude-fable-5-2-high, claude-opus-5-5-high, claude-sonnet-5-5-high
arena cross-judge pool: claude-fable-5-2-high, claude-opus-5-5-high, claude-sonnet-5-5-high
swarm workers: claude-opus-5-5-high
architect runners: claude-fable-5-2-high, claude-opus-5-5-high, claude-sonnet-5-5-high
interrogate reviewers: claude-fable-5-2-high, claude-opus-5-5-high, claude-sonnet-5-5-high
