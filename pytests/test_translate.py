"""Every example law in the README translates to the template it's listed under."""

import pytest

from swarmcontrol.laws.translate import translate_deterministic

EXAMPLES = [
    ("Agents must not modify /repo/test/ or .env.", "protected_resources", {"protectedPaths": ["/repo/test/", "/repo/.env"]}),
    ("Never edit package.json.", "protected_resources", {"protectedPaths": ["/repo/package.json"]}),
    ("Reviewers must not use Bash.", "tool_restriction", {"blockedTools": ["Bash"]}),
    ("Agents must not use WebFetch or mcp__github__*.", "tool_restriction", {"blockedTools": ["WebFetch", "mcp__github__*"]}),
    ("Agents should read progress.md before making changes.", "required_reading", {"paths": ["/repo/progress.md"]}),
    ("Agents that modify /repo/src/ must run npm test before finishing.", "conditional_obligation", {"whenWrites": ["/repo/src/"], "whenTools": [], "mustRun": "npm test"}),
    ("Agents must not make more than three consecutive unsuccessful attempts.", "bounded_retries", {"maxAttempts": 3}),
    ("Agents must not claim a task is complete until all checks pass.", "task_completion", {}),
    ("Every claim must cite at least two independent sources.", "evidence_requirements", {"minSources": 2}),
    ("Reports should sound professional.", "contextual", {}),
]


@pytest.mark.parametrize("text,template,params", EXAMPLES)
def test_readme_examples(text, template, params):
    rule = translate_deterministic(text)[0]
    assert (rule["template"], rule["params"]) == (template, params)
    assert rule["issues"] == [] or template == "contextual"
