# Demo video

- [`swarmcontrol-demo.mp4`](swarmcontrol-demo.mp4): 71 seconds, 1920×1200, captioned, no audio.
- [`swarmcontrol-demo.webp`](swarmcontrol-demo.webp): a 28-second highlight for the README (engineers corrected, the lead escalates, a human approves, the run finishes).

**The story:** a team of Claude Code agents ships a release with three tickets. A new law says agents that change source code must run the tests before finishing. One of QA's tests is wrong, so the release gate can't pass until a human steps in.

## What's real, and what isn't literal

- **The session is real:** Claude Haiku 5.5 in Claude Code 2.1.316, recorded on November 13, 2026: a lead and three engineer subagents, in `acceptEdits` permission mode, inside a macOS sandbox that only lets it write to the demo folder. The run took 18 turns.
- **Everything on the dashboard happened as shown:** the law was typed into the Laws page and translated by the deterministic translator; each engineer tried to finish without running `npm test`, was blocked once, ran it and finished; the lead's done check (the release gate) failed four times, after which it escalated.
- **A script played the human:** it fixed QA's test and approved in the dashboard with the note shown. The terminal cards are shortened replays and are labelled as such; the fix card shows the equivalent `sed` command.
- **Sped-up parts are labelled** in the top-right corner (1.3× to 7.7×). From the first engineer starting to the lead escalating took about 40 seconds; the lead finished about 5 seconds after the approval.
- **The law scene and the trajectory scene are pickup shots** of the same server, recorded right after the run (the trajectory is the recorded run; the law was re-typed so the generated rule is on screen).
- **This is a staged conflict:** the wrong test is planted, using the delegated-team benchmark's method. Don't present it as a customer incident.

Upload `swarmcontrol-demo.mp4` through GitHub's editor (drag it into the README or a release) to get an inline player; GitHub doesn't play videos committed to the repository.
