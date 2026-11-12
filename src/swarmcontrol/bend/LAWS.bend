# Formal properties of the runtime gates in governor.bend.
# Each law is an open claim until PROOF.bend proves it; `bend PROOF.bend`
# prints ALL PROOFS CHECK only when every law below holds.
import Base
import ./governor.bend as G

# Law 1a: a write to any protected resource is blocked.
law protected_write_blocked:
  for r: Nat
  for ps: List<&2, Nat>
  for e: {G.elem(r, ps) == True{} : Bool}
  {G.write_gate(r, ps) == G.Block{} : G.Decision}

# Law 1b: the gate does not over-block: unprotected writes are allowed.
law unprotected_write_allowed:
  for r: Nat
  for ps: List<&2, Nat>
  for e: {G.elem(r, ps) == False{} : Bool}
  {G.write_gate(r, ps) == G.Allow{} : G.Decision}

# Law 2: once attempts reach the budget, every further attempt escalates.
law retry_budget_escalates:
  for max: Nat
  for k: Nat
  {G.retry_gate(Nat.add(max, k), max) == G.Escalate{} : G.Decision}

# Law 3: any number of citations from one domain never satisfies a
# requirement of two or more independent sources.
law single_domain_insufficient:
  for d: Nat
  for n: Nat
  for k: Nat
  {G.evidence_gate(2n+k, List.replicate(Nat, 1n+n, d)) == G.Block{} : G.Decision}

# Law 4: a single failed check anywhere in the checklist blocks completion.
law failed_check_blocks_completion:
  for pre: List<&2, Bool>
  for post: List<&2, Bool>
  {G.completion_gate(List.append(&2, Bool, pre, False{} <> post)) == G.Block{} : G.Decision}

# Law 5a: any amount above the cap is blocked, however far above it is.
law over_cap_blocked:
  for cap: Nat
  for k: Nat
  {G.spend_gate(Nat.add(cap, 1n+k), cap) == G.Block{} : G.Decision}

# Law 5b: the gate does not over-block: amounts up to the cap are allowed.
law within_cap_allowed:
  for amount: Nat
  for k: Nat
  {G.spend_gate(amount, Nat.add(amount, k)) == G.Allow{} : G.Decision}

# Law 6a: an item missing from the allowlist is always blocked.
law unlisted_blocked:
  for r: Nat
  for xs: List<&2, Nat>
  for e: {G.elem(r, xs) == False{} : Bool}
  {G.allow_gate(r, xs) == G.Block{} : G.Decision}

# Law 6b: an allowlisted item is never blocked.
law listed_allowed:
  for r: Nat
  for xs: List<&2, Nat>
  for e: {G.elem(r, xs) == True{} : Bool}
  {G.allow_gate(r, xs) == G.Allow{} : G.Decision}
