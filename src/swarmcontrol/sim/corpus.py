"""Synthetic research corpus for the default experiment. All publishers use the reserved `.example` TLD: these are
simulated sources, not real citations. Each topic: findings (each <= 60 words), a long finding (> 60 words, used by
the constraint-violation fault), and three publishers; publisher 0 also has a `blog.` subdomain source, so the corpus
contains two URLs that are NOT independent despite different hostnames."""

from __future__ import annotations

from functools import cache

RESEARCH_QUESTION = 'Research the future of AI agent infrastructure and produce a structured report identifying important trends, supporting evidence, and potential business opportunities.'

TOPICS: list[dict] = [{'id': 'orchestration',
  'name': 'Agent orchestration',
  'trend': 'Orchestration is moving from free-form loops to explicit graphs with typed state and checkpoints.',
  'opportunity': 'Checkpoint-native orchestration layers that expose interception points for policy engines.',
  'findings': ['Production agent systems increasingly model work as explicit graphs with persisted state, which '
               'makes every transition a natural checkpoint for inspection and policy.',
               'Teams report that free-form tool loops are hard to debug at scale; bounded, resumable steps are '
               'replacing open-ended agent loops.',
               'Orchestrators are converging on durable execution so long-running agent tasks survive restarts and '
               'can be replayed deterministically.'],
  'longFinding': 'Orchestration frameworks for agents are evolving rapidly and there are many different approaches '
                 'being explored across the industry, including graph-based systems, actor-based systems, durable '
                 'workflow engines, event-driven pipelines and hybrid designs, and each of these approaches has '
                 'different strengths and weaknesses that teams need to consider carefully depending on their '
                 'workloads, latency budgets, failure tolerance and the maturity of their internal platform teams '
                 'over time.',
  'publishers': [{'domain': 'agentsystems-review.example', 'publisher': 'Agent Systems Review'},
                 {'domain': 'workflow-quarterly.example', 'publisher': 'Workflow Quarterly'},
                 {'domain': 'distsys-notes.example', 'publisher': 'DistSys Notes'}]},
 {'id': 'security',
  'name': 'Runtime security',
  'trend': 'Security focus is shifting from prompt filtering to enforcing what agents may actually do at the tool '
           'boundary.',
  'opportunity': 'Tool-boundary policy enforcement with audit trails that satisfy security review.',
  'findings': ['Prompt-level guardrails do not prevent a compromised agent from calling a dangerous tool; '
               'enforcement has to happen where actions execute.',
               'Least-privilege tool permissions per agent role reduce blast radius when an agent is manipulated by '
               'untrusted content.',
               'Security teams want deterministic, auditable decisions for agent actions rather than model-judged '
               'approvals.'],
  'longFinding': 'Runtime security for autonomous agents involves a wide range of concerns that include prompt '
                 'injection, data exfiltration, privilege escalation, supply chain risk in tools and plugins, '
                 'credential handling, sandboxing of code execution, network egress control, and the organizational '
                 'processes needed to review and approve agent capabilities, all of which interact in complex ways '
                 'that most organizations have not yet fully mapped or addressed in their current deployments.',
  'publishers': [{'domain': 'secops-journal.example', 'publisher': 'SecOps Journal'},
                 {'domain': 'appsec-weekly.example', 'publisher': 'AppSec Weekly'},
                 {'domain': 'trust-boundary.example', 'publisher': 'Trust Boundary'}]},
 {'id': 'observability',
  'name': 'Observability',
  'trend': 'Trace volume from multi-agent systems is outgrowing manual inspection.',
  'opportunity': 'Swarm-level health summaries that triage which agents need a human.',
  'findings': ['Multi-agent runs generate traces too large to read by hand; developers need aggregate health signals '
               'that point to the few agents worth inspecting.',
               'Trajectory-level views that connect an action to the decision that allowed it are more useful for '
               'debugging than raw token logs.',
               'Observability tools explain failures after the fact but rarely intervene while the run is still in '
               'progress.'],
  'longFinding': 'Observability for agent systems borrows heavily from distributed tracing, logging and metrics '
                 'practices, but agents add new dimensions such as reasoning traces, tool call arguments, '
                 'intermediate artifacts, model versions, prompt templates and evaluation results, and teams '
                 'struggle to decide which of these signals to keep, how long to retain them, how to correlate them '
                 'across agents, and how to present them to developers in a way that is actionable.',
  'publishers': [{'domain': 'tracing-today.example', 'publisher': 'Tracing Today'},
                 {'domain': 'devtools-digest.example', 'publisher': 'DevTools Digest'},
                 {'domain': 'sre-letters.example', 'publisher': 'SRE Letters'}]},
 {'id': 'evaluation',
  'name': 'Evaluation and reliability',
  'trend': 'Reliability work is moving from offline benchmarks to runtime checks on live trajectories.',
  'opportunity': 'Runtime evaluators that turn task specs into enforceable completion checks.',
  'findings': ['Agents frequently report success before required checks pass; explicit completion checklists catch '
               'these false success claims.',
               'Offline benchmarks miss failure modes that only appear in long trajectories, motivating evaluation '
               'at runtime checkpoints.',
               'Bounded retries with corrective feedback recover many transient failures without human involvement.'],
  'longFinding': 'Evaluating agent reliability is challenging because tasks are open-ended, outcomes can be '
                 'partially correct, failures compound across steps, evaluation itself can be noisy when it relies '
                 'on model judges, and the distribution of real tasks in production rarely matches the benchmarks '
                 'that teams use during development, so organizations end up combining many partial signals into '
                 'dashboards that are hard to interpret and even harder to act on consistently.',
  'publishers': [{'domain': 'eval-methods.example', 'publisher': 'Eval Methods'},
                 {'domain': 'reliability-lab.example', 'publisher': 'Reliability Lab'},
                 {'domain': 'ml-practice.example', 'publisher': 'ML Practice'}]},
 {'id': 'economics',
  'name': 'Inference economics',
  'trend': 'Swarm cost is dominated by wasted work: retries, loops and abandoned trajectories.',
  'opportunity': 'Budget-aware runtimes that stop unproductive loops early.',
  'findings': ['Unbounded retry loops are a significant source of wasted tokens in agent swarms; stopping them early '
               'saves cost even when the task still fails.',
               'Recovery prompts add tokens, so governance has a measurable cost that must be weighed against '
               'avoided failures.',
               'Smaller models handle routine subtasks while larger models are reserved for synthesis and recovery.'],
  'longFinding': 'The economics of inference for agents depend on many factors including model choice, prompt '
                 'length, context reuse, caching strategies, batch processing, tool call frequency, retries, '
                 'parallelism, the ratio of input to output tokens, and the pricing models of different providers, '
                 'which change frequently and make it difficult for teams to forecast spending or compare '
                 'architectures without careful instrumentation of their production workloads.',
  'publishers': [{'domain': 'compute-ledger.example', 'publisher': 'Compute Ledger'},
                 {'domain': 'unit-economics.example', 'publisher': 'Unit Economics'},
                 {'domain': 'finops-brief.example', 'publisher': 'FinOps Brief'}]},
 {'id': 'coordination',
  'name': 'Multi-agent coordination',
  'trend': 'Shared state between agents needs ownership rules, or agents overwrite each other.',
  'opportunity': 'Coordination primitives that protect shared resources across agents.',
  'findings': ['When many agents share a workspace, unprotected shared files get overwritten; explicit ownership of '
               'resources prevents silent corruption.',
               'Coordinator agents that merge sub-results work best when inputs are structured and validated before '
               'merging.',
               'Agents that escalate early with context are cheaper to resolve than agents that fail late without '
               'it.'],
  'longFinding': 'Coordination among multiple agents raises questions about communication protocols, shared memory, '
                 'task decomposition, role assignment, conflict resolution, consensus, and how to merge partial '
                 'results, and current systems take very different approaches ranging from strict hierarchies with a '
                 'single planner to loosely coupled marketplaces where agents bid on tasks, with little agreement '
                 'yet about which patterns generalize across domains and workloads.',
  'publishers': [{'domain': 'multiagent-letters.example', 'publisher': 'Multi-Agent Letters'},
                 {'domain': 'collab-systems.example', 'publisher': 'Collaborative Systems'},
                 {'domain': 'swarm-notes.example', 'publisher': 'Swarm Notes'}]},
 {'id': 'deployment',
  'name': 'Deployment infrastructure',
  'trend': 'Agents are being deployed as long-lived services with sandboxes and per-tool credentials.',
  'opportunity': 'Sandboxed agent runtimes with policy enforcement built in.',
  'findings': ['Agent deployments are adopting sandboxed execution environments with scoped credentials instead of '
               'sharing host access.',
               'Platform teams want a single control point to change agent policies without redeploying every agent.',
               'Rollouts of new agent behaviors increasingly use staged deployment with automatic rollback on policy '
               'violations.'],
  'longFinding': 'Deployment infrastructure for agents spans container orchestration, serverless functions, GPU '
                 'scheduling, secrets management, network policy, artifact storage, versioning of prompts and tools, '
                 'continuous delivery pipelines and incident response, and organizations are still working out which '
                 'of these responsibilities belong to platform teams, which belong to application teams, and how to '
                 'share them across many concurrently running agents.',
  'publishers': [{'domain': 'platform-eng.example', 'publisher': 'Platform Engineering'},
                 {'domain': 'cloudops-review.example', 'publisher': 'CloudOps Review'},
                 {'domain': 'infra-dispatch.example', 'publisher': 'Infra Dispatch'}]},
 {'id': 'market',
  'name': 'Market opportunities',
  'trend': 'Buyers ask for proof of control before granting agents production access.',
  'opportunity': 'A governance control plane that sits between agent frameworks and tools.',
  'findings': ['Enterprise buyers cite lack of enforceable controls as a blocker for giving agents write access to '
               'production systems.',
               'Vendors that combine observability with enforcement can sell to both platform and security teams.',
               'Demand is growing for audit evidence that specific agent actions were prevented, not merely logged.'],
  'longFinding': 'The market for agent infrastructure includes model providers, orchestration frameworks, '
                 'observability vendors, security vendors, evaluation platforms, data infrastructure companies and '
                 'consultancies, and the boundaries between these categories are shifting quickly as products '
                 'expand, so it remains unclear which categories will consolidate, which will remain independent, '
                 'and where long-term value will accrue as enterprises standardize their agent platforms.',
  'publishers': [{'domain': 'enterprise-signal.example', 'publisher': 'Enterprise Signal'},
                 {'domain': 'saas-analyst.example', 'publisher': 'SaaS Analyst'},
                 {'domain': 'buyer-survey.example', 'publisher': 'Buyer Survey'}]}]

ANGLES = ['current trends',
 'supporting evidence',
 'failure modes',
 'key players and approaches',
 'metrics that matter',
 'business opportunities',
 'open problems',
 'adoption blockers',
 'architecture patterns',
 'cost drivers',
 'risks',
 'near-term roadmap',
 'buyer requirements']


def topics() -> list[dict]:
    return TOPICS


def topic_by_id(topic_id: str) -> dict:
    return next(t for t in TOPICS if t["id"] == topic_id)


def subtask_for(index: int) -> dict:
    t = TOPICS[index % len(TOPICS)]
    angle = ANGLES[(index // len(TOPICS)) % len(ANGLES)]
    return {"topic": t["name"], "topicId": t["id"], "angle": angle,
            "question": f"{t['name']}: {angle}. Produce at least two findings, each supported by two independent sources."}


@cache
def sources() -> tuple[dict, ...]:
    """Six sources per topic across three publishers; one publisher appears twice."""
    out: list[dict] = []
    for t in TOPICS:
        a, b, c = t["publishers"]

        def mk(n: int, host: str, p: dict, title: str) -> None:
            # domain: the hostname from metadata; independence uses its registrable domain
            out.append({"id": f"{t['id']}-s{n}", "title": title, "url": f"https://{host}/{t['id']}/{n}", "domain": host,
                        "publisher": p["publisher"], "topicId": t["id"], "snippet": t["findings"][n % len(t["findings"])]})

        mk(1, a["domain"], a, f"{t['name']}: state of practice")
        mk(2, f"blog.{a['domain']}", a, f"{t['name']}: field notes")
        mk(3, b["domain"], b, f"{t['name']}: practitioner survey")
        mk(4, b["domain"], b, f"{t['name']}: case studies")
        mk(5, c["domain"], c, f"{t['name']}: design patterns")
        # one source with missing domain metadata (an unattributed mirror)
        out.append({"id": f"{t['id']}-s6", "title": f"{t['name']}: reposted summary (unattributed)", "url": f"https://mirror.invalid/{t['id']}",
                    "domain": None, "publisher": "unknown", "topicId": t["id"], "snippet": t["findings"][0]})
    return tuple(out)


def source_by_id(source_id: str) -> dict | None:
    return next((s for s in sources() if s["id"] == source_id), None)


def sources_for_topic(topic_id: str) -> list[dict]:
    return [s for s in sources() if s["topicId"] == topic_id]
