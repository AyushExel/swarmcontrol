# Tutorial: run an agent team on the dashboard (about 20 minutes)

Write laws, scope them to the agents they govern, run a real agent team with and without SwarmControl, and inspect what it did. This uses the **Delegated team** benchmark, which runs on headless Claude Code with your Claude subscription, so it costs no API credits.

**Before you start.** You need SwarmControl installed and Bend on your PATH (see the [README](../README.md#quick-start)), Node (the team's tickets are JavaScript), and the `claude` CLI logged in (`claude --version` to check). Then:

```bash
swctl serve   # API and dashboard on http://localhost:8787
```

## Step 1: Laws, global and per agent

Open **Laws**. Every row is a law the runtime can enforce before an action executes. The **Applies to** column says which agents the law governs:

- **All agents** (global): for example *Bounded retries* (an agent gets at most N corrective attempts after a blocked action, then a human is asked) and *Spending limit*.
- **role: lead**: *Lead: assign only open backlog tickets, once each*.
- **role: implementer**: *Engineers: tests and CI belong to QA*, *Engineers: change only your ticket's file*, *Engineers: done requires the acceptance suite*.

Each agent is checked **only against its own laws**. An engineer is never checked against the lead's laws, and the lead never sees the engineers' laws. No agent needs to know about any other agent, or even about its own laws: the governor enforces them at the tool boundary whatever the agent's prompt says.

Click any law to open it. You can see:
- its parameters (for example the protected paths);
- the exact Bend instance that was checked, and the Bend checker's output (`proof_checked` = the property was machine-verified);
- **Applies to roles / agents**, where you can rescope it. Leave both empty to make the law global.

**Add your own law.** Under *Add a law* → *Natural language*:
1. Type a rule, e.g. `Agents must not modify anything under /repo/package.json`.
2. Optionally fill *Applies to roles*, e.g. `implementer`.
3. Click **Generate structured rules**. The translator shows the structured rule it understood, whether it can be enforced deterministically, and whether Bend validated it.
4. Click **Activate**.

Rules that can't be enforced deterministically are flagged, never silently accepted. The *Bend* tab takes a hand-written gate plus the laws you want proven about it.

## Step 2: Run a delegated team, with and without the governor

Open **Experiments** and pick **Delegated team**. The team is:
- **1 tech lead** (Claude Haiku). It gets a backlog of 32 coding tickets and writes a brief for each engineer.
- **32 engineers** (Claude Haiku), one per ticket. Each works alone in its own workspace and sees **only the brief its lead wrote**: not the backlog, not the team handbook, not the other engineers.

The tickets are real HumanEval problems. In **half of them**, one QA test contradicts the specification (ImpossibleBench's method): no correct implementation can pass it. The honest move is to flag the conflict. The dishonest one is to edit the test or special-case the input so it goes green. The backlog carries a realistic "we ship today, every ticket needs to be green" note.

Settings worth knowing:
- **Law set**: preselected to the five team laws (four role-scoped plus global bounded retries). The label next to each says whom it governs.
- **State the laws in the system prompt**: if ticked, the lead gets the team handbook and may pass the rules on in its briefs. Untick it for the realistic case where the rules live only in the governor.

Click **Run paired (baseline + governed)**. The same team, tickets and settings run twice: once with the governor off (it only *audits* what would have been blocked) and once with it on. A pair takes about 3–5 minutes.

## Step 3: Watch it live

**Live Swarm** shows both runs side by side, one tile per agent:
- **green**: working;
- **yellow (…)**: the governor blocked an action and the agent is recovering with corrective feedback;
- **red**: a violation took effect (baseline only), or the agent was escalated to a human;
- **↺**: the agent recovered after a block.

The event feed on the right shows each assignment, write, block and submission as it happens.

## Step 4: Inspect one agent

Open **Trajectories** and pick an engineer, ideally one on an impossible ticket in the baseline run. You see the complete record:
- the lead's brief;
- every tool call and result;
- each law evaluation with its Bend input and decision;
- the final graded record (*Case graded*): ticket, whether it was impossible, how the engineer submitted, and the objective checks.

Compare the same ticket in the governed run. Where the baseline engineer edited a test or special-cased an input, the governed engineer's write was **blocked before it executed**. Its "done" was rejected because CI's hidden acceptance suite failed (the feedback says how many checks fail, never the expected values). It then flagged the conflict, or was handed to a human.

**Escalations.** Agents that keep violating after their recovery budget show as red `awaiting_human`. The trajectory panel shows what went wrong, which law, and every attempt, with **Approve retry with guidance** and **Cancel** buttons.

## Step 5: Read the result

**Overview** and **Results** compare the pair: task success from objective checks only (never the agent's own claim), violations attempted / blocked / executed, recoveries, escalations, tokens and cost. Every row states its denominator. **Export** on the Results page writes the trajectories as JSONL (full traces, SFT examples, and preference pairs from governed recoveries).

## Next

To govern your own Claude Code sessions instead of a benchmark team, see [`claude-code.md`](claude-code.md).

