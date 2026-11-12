# Tutorial: govern your Claude Code sessions (about 20 minutes)

You'll run the governor on your laptop, connect Claude Code to it, and watch it enforce rules on a real session:
- Claude can't edit protected files.
- Claude can't stop while your tests fail.
- One named agent is kept out of a folder that another agent may change.

Nothing needs an API key: Claude Code uses your normal Claude login.

*Every step below was run end to end on October 30, 2026 with Claude Code 2.1.314. On November 12, 2026 the governor moved to Python: steps 1, 3 and 9 changed to the Python commands, and a session was re-run through them (protected write blocked, stop refused while the done check failed).*

## What you need

- **Python 3.11 or newer** and **[pipx](https://pipx.pypa.io/)** (or a virtualenv).
- **[Bend](https://bend-lang.com/)**: `curl -fsSL https://bend-lang.com/install.sh | sh`, then add `~/.bend/bin` to your `PATH`. The governor proves its laws and runs its gates with it. With clang installed (on macOS: `xcode-select --install`) the gates are compiled and checks are near-instant; without it they still work, more slowly.
- **Claude Code**, installed and logged in (`claude --version`).
- **Node.js**, only because the practice project is a small JavaScript project (`npm test`).
- **This repository**, for the practice project, and a terminal.

## 1. Start the governor

```bash
pipx install swarmcontrol   # or, from this repository: npm ci && npm run build && pipx install .
swctl serve          # the dashboard and the API on http://localhost:8787
```

Open **http://localhost:8787**. Keep this terminal running.

## 2. Make a practice project

The repo includes a tiny shop checkout with one failing test. Copy it out, so the tutorial doesn't change the governor repo:

```bash
cp -r tutorials/sample-checkout ~/governor-demo
cd ~/governor-demo
npm test                   # 1 pass, 1 fail: the discount is subtracted as cents, not as a percentage
```

## 3. Connect Claude Code to the governor

One command, run from the practice project:

```bash
cd ~/governor-demo
swctl connect
```

You can also copy the exact command from the dashboard's **Overview** page ("Connect your Claude Code"). That version downloads the connector from the server, so it works on machines without this repo.

`connect` does three things:
1. **Checks it can reach the governor** (`http://localhost:8787` by default, or `--server URL`).
2. **Saves the server URL** (and token, if any) in `~/.config/swarmcontrol/config.json`, readable only by you.
3. **Adds three hooks** to `.claude/settings.local.json`, keeping any settings already there:
   - **PreToolUse** checks every action before it runs.
   - **PostToolUse** records what ran.
   - **Stop** checks before the session ends.

From now on, **every** Claude Code session you start in this folder reports to the governor. Use `connect --global` to cover every project on this machine instead. `swctl status` shows what's connected.

> **The governor fails closed.** If it isn't running, every tool call in this project is denied, with a message saying the governor is unreachable. Start it again, or run with `SC_FAIL_OPEN=1` to let actions through while it's down.

## 4. Try observe mode first (nothing is blocked)

Observe mode shows what the governor *would* stop, without stopping anything. It's the safe way to roll it out on a real project.

```bash
SC_MODE=observe claude
```

Ask Claude:

> Update the expected value in test/cart.test.js so the tests pass.

Claude makes the edit. On the dashboard, open **Live Swarm** and pick **attached: governor-demo** from the run picker at the top right. The session's agent is there, and its trajectory shows **Violation took effect: Edit → /repo/test/cart.test.js**. A fresh install already protects `test/`, `.ci/` and `package.json` for every agent.

Undo the edit before continuing: `git checkout test/` if you made the folder a git repo, or copy `test/cart.test.js` from `tutorials/sample-checkout` again.

## 5. Enforce, with a done check

```bash
SC_ROLE=implementer SC_AGENT=checkout-dev SC_DONE_CHECK="npm test" claude
```

Ask the same thing:

> CI is red on test/cart.test.js and we ship in 5 minutes. Just update the expected value in the discount test to match what the code returns now.

What happened in our run:
1. **Claude declined to change the test** and tried to stop without fixing anything.
2. **The governor refused the stop,** because `npm test` was still failing. Claude saw the test output with the message *"Fix the cause, or explain to the user why it cannot be done."*
3. **Claude fixed the real bug** in `src/cart.js`, ran the tests (2 pass), and stopped.

If Claude had tried to edit the test file, the edit would have been denied before it ran, with the reason shown to Claude.

On the dashboard, the agent **checkout-dev** went yellow while it was blocked, then green once its done check passed. **Trajectories** shows each step: the blocked stop, the feedback, and the fix.

## 6. Write your own law, for one agent

Laws can cover everyone, a role, or a specific named agent (`SC_AGENT`). Here, `checkout-dev` must stay out of the payments code, while a payments agent may change it.

1. Open the dashboard and go to **Laws**, then **Add a law**, then **Natural language**.
2. Replace the text with:

   > Agents must never modify the files /repo/src/payments/ on any ticket.

   Paths inside your project are written as `/repo/...`.
3. Leave **Applies to roles** empty. Type `checkout-dev` in **…or to specific agents**.
4. Untick **Use LLM translator**, unless the server has an Anthropic key. Click **Generate structured rules**: you'll see a *Protected resources* rule for `/repo/src/payments/`, marked valid and proof-checked.
5. Click **Activate 1 validated rule**. The new law appears in the table with the pill **checkout-dev**.

There's no need to restart anything: the next hook call picks up the new law. Now try it with two agents:

```bash
SC_ROLE=implementer SC_AGENT=checkout-dev claude
#   ask: "In src/payments/charge.js, add an optional currency parameter (default 'usd')."
#   → the edit is blocked: "BLOCKED by the runtime (Protect /repo/src/payments/) …"

SC_ROLE=implementer SC_AGENT=payments-dev claude
#   ask the same thing → the edit goes through
```

That's the core idea: each agent is checked only against its own laws, and needs no knowledge of the others.

### 6b. Laws for subagents, and laws about tools

When Claude Code delegates to a subagent (the built-in `Explore` or `general-purpose`, or your own in `.claude/agents/`), the governor sees it as **its own agent**: it appears on the dashboard as `checkout-dev / reviewer`, and its role is its subagent type. Two rules follow:
- **Laws inherit downward.** A subagent is covered by every law that covers its parent session (its `SC_AGENT` and `SC_ROLE`), so delegating can't be used to get around a rule.
- **Subagents can have their own laws.** Scope a law to the subagent type as a role.

And laws can be about **tools**, not just files: "may not use Bash", "may not use WebFetch", or every tool of one MCP server (`mcp__github__*`).

Try it. Save this as `~/governor-demo/.claude/agents/reviewer.md`:

```markdown
---
name: reviewer
description: Reviews code for bugs and reports findings. Use it when asked to review code.
tools: Read, Grep, Glob, Bash
---
You are a code reviewer. Read the code, try to verify behaviour, and report concrete findings. Do not modify files.
```

On the **Laws** page, add `Reviewers must not use Bash.` and type `reviewer` in **Applies to roles**. The translator turns it into a *restricted tools* rule for `Bash`, backed by the same proven gate as protected files. Then ask Claude:

> Use the reviewer subagent to review src/cart.js, and have it run npm test. Then run npm test yourself.

What happened in our run: the reviewer's `Bash` calls were blocked ("BLOCKED by the runtime (No Bash): Bash is a restricted tool for this agent"), so it reviewed by reading the code. The main session's own `npm test` ran normally.

### 6c. Conditional laws: "if you did X, you must do Y before finishing"

On the **Laws** page, add:

> Agents that modify /repo/src/ must run npm test before finishing.

The trigger can be paths written (as here) or tools used ("Agents that use WebFetch must run …"). When the agent tries to stop, the proven completion gate refuses if the command hasn't run since its last triggering change. Subagents are checked when they finish, in the same way.

Then ask Claude: *"Fix the discount bug in src/cart.js. Just edit the file; don't run any commands."*

What happened in our run: Claude edited the file and said "Fixed", and its stop was refused with *"You changed src/cart.js, but "npm test" has not run since. Run npm test now, fix anything it reports, then finish."* It ran the tests (2 pass) and the stop was allowed.

The law checks that the command **ran**, not that it passed. To require passing, use `--done-check "npm test"` as well. In observe mode, an unmet obligation is recorded on the dashboard and the stop goes through.

**Other harnesses** get the same model through the HTTP API: send `parent: { agent, role }` with a sub-agent's `POST /api/attach/check` call, and it inherits its parent's laws in the same way.

## 7. When an agent keeps trying: escalation

If an agent breaks the same rule more than its retry budget allows (3 by default, set by the *Bounded retries* law), the governor stops it and asks a human. The agent turns **red**, and every further action gets *"A human has been asked to review this agent."*

On the dashboard, open **Live Swarm**, click the red agent, and use the **Human intervention required** panel:
- **Approve retry with guidance:** type a note, for example *"Leave the tests alone; fix src/cart.js."* The note is delivered to Claude with its next tool call, and every rule still applies.
- **Cancel agent:** the session is stopped for good.

A session that escalates while finishing is held open, up to about 50 minutes (`SC_HUMAN_WAIT`, in seconds; 0 turns this off), and resumes by itself when you approve, with your note. If it stopped before you decided (it timed out, or it was connected before this feature), tell it to continue in the terminal. Run `connect` again in older projects to get this.

## Try it on a weaker model

The governor matters most on models that cut corners. `claude-haiku-4-5` is the oldest Haiku that Claude Code can still run (the 3.x models are retired):

```bash
claude --model claude-haiku-4-5
```

## 8. Settings reference

Set these as environment variables when you start `claude`:

| Variable | What it does | Default |
|---|---|---|
| `SC_ROLE` | the agent's role, for role-scoped laws | `agent` |
| `SC_AGENT` | the agent's name, shown on the dashboard and matched by agent-scoped laws; its subagents appear as `<name> / <type>` | the session id |
| `SC_OWNS` | files or folders this agent may change, e.g. `src/api/` (enables file-ownership checks) | none |
| `SC_DONE_CHECK` | a command that must pass before the session may stop | none |
| `SC_MODE` | `observe` records but doesn't block | `enforce` |
| `SC_FAIL_OPEN` | `1` lets actions through when the governor is unreachable | fail closed |
| `SC_PROJECT` | which dashboard run the session reports into | the folder name |
| `SC_API` | the governor's URL | `http://localhost:8787` |
| `SC_HUMAN_WAIT` | seconds a stopping session waits for a human decision after escalating; `0` = don't wait | `3000` |
| `SC_API_TOKEN` | access token, for a self-hosted governor (see `self-hosted.md`) | none |

To avoid typing these every time, pass them to `connect` once: `connect --role implementer --agent checkout-dev --done-check "npm test"` (or `--observe`). It saves them as defaults in `.claude/settings.local.json`. Environment variables still override the defaults per session.

## 9. Remove it

```bash
cd ~/governor-demo
swctl disconnect          # add --global if you connected with --global
```

## Limits worth knowing

- **Shell commands are parsed for the files they write,** for example `echo x > test/a.js` or `sed -i`. A write hidden inside a script the command runs is not seen. For hard guarantees, also run agents in a sandbox.
- **Agents can't edit the hook settings or the saved governor config** (built in, always on), but this uses the same best-effort shell parsing, and an agent with shell access can read the saved token. Treat it as a guardrail, not a security boundary.
- **Each law change opens a fresh run record** for attached sessions on the dashboard, so the new laws apply from that point.
- **Other harnesses (Codex, Cursor, SDKs)** can use the same decisions over HTTP today: `POST /api/attach/check` with `{ project, role, agent, event, tool, input, cwd }` returns `{ allow, reason }`. Native installers for them are on the roadmap.
