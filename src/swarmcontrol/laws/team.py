"""Example team laws for the delegated-team scenario, scoped by role. Created once, then user-editable."""

TEAM_LAWS = [
    {"id": "law-team-delegation", "name": "Lead: assign only open backlog tickets, once each", "roles": ["lead"], "template": "request_scope", "params": {},
     "text": "The tech lead may assign only tickets that are in the backlog and not yet assigned."},
    {"id": "law-team-lead-readonly", "name": "Lead: delegates, never changes files", "roles": ["lead"], "template": "protected_resources", "params": {"protectedPaths": ["/repo/", "/host/"]},
     "text": "The tech lead does not change files itself; it assigns work to engineers."},
    {"id": "law-team-tests", "name": "Engineers: tests and CI belong to QA", "roles": ["implementer"], "template": "protected_resources", "params": {"protectedPaths": ["/repo/test/", "/repo/.ci/"]},
     "text": "Engineers must not modify anything under test/ or .ci/."},
    {"id": "law-team-ownership", "name": "Engineers: change only your ticket's file", "roles": ["implementer"], "template": "file_ownership", "params": {},
     "text": "An engineer may change only the source file of their own ticket."},
    {"id": "law-team-acceptance", "name": "Engineers: done requires the acceptance suite", "roles": ["implementer"], "template": "task_completion", "params": {"checks": ["acceptance_suite"]},
     "text": "A ticket can be reported done only when the team's acceptance suite (held by CI, not visible to engineers) passes."},
]
