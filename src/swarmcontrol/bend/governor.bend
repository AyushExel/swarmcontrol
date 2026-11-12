# Runtime gate functions for the Agent Swarm Runtime Governor.
#
# These are the functions the runtime actually executes at checkpoints: this
# file is compiled with `bend governor.bend -o governor.mjs` and imported by the
# Node runtime. LAWS.bend states properties of these exact functions and
# PROOF.bend proves them, so the code that enforces a law is the code the
# proofs are about.
#
# Resources, source domains and checks are passed in as Nat / Bool values; the
# TypeScript adapter maps sandbox paths and source metadata to these ids.
import Base

type Decision is Data:
  Allow{}
  Block{}
  Escalate{}

# --- shared helpers -------------------------------------------------------

def elem(+r: Nat, ps: +List<Nat>) -> Bool:
  match ps:
    case Nil{}:
      False{}
    case Con{h, t}:
      Bool.or(Nat.is_eq(r, h), elem(r, t))

def lt(a: Nat, b: Nat) -> Bool:
  match a b:
    case 0n 0n:
      False{}
    case 0n 1n+q:
      True{}
    case 1n+p 0n:
      False{}
    case 1n+p 1n+q:
      lt(p, q)

def block_if(b: Bool) -> Decision:
  match b:
    case True{}:
      Block{}
    case False{}:
      Allow{}

def escalate_unless(b: Bool) -> Decision:
  match b:
    case True{}:
      Allow{}
    case False{}:
      Escalate{}

# --- Law 1: protected resources (pre-action) ------------------------------

# Block a write whose target resource id is in the protected set.
def write_gate(+r: Nat, ps: +List<Nat>) -> Decision:
  block_if(elem(r, ps))

# --- Law 2: bounded retries (trajectory) ----------------------------------

# Allow another recovery attempt only while attempts < max; otherwise escalate.
def retry_gate(attempts: Nat, max: Nat) -> Decision:
  escalate_unless(lt(attempts, max))

# --- Law 3: evidence requirements (post-action) ---------------------------

# Number of distinct source domains (a domain repeated counts once).
def distinct.step(rest: Nat, seen: Bool) -> Nat:
  match seen:
    case True{}:
      rest
    case False{}:
      1n+rest

def distinct(ds: +List<Nat>) -> Nat:
  match ds:
    case Nil{}:
      0n
    case Con{+h, +t}:
      distinct.step(distinct(t), elem(h, t))

# Block a final claim backed by fewer than `min` independent domains.
def evidence_gate(min: Nat, ds: +List<Nat>) -> Decision:
  block_if(lt(distinct(ds), min))

# --- Law 4: task completion (post-action) ---------------------------------

def all_true(cs: List<&2, Bool>) -> Bool:
  match cs:
    case Nil{}:
      True{}
    case Con{h, t}:
      Bool.and(h, all_true(t))

# Block a completion claim unless every required check passed.
def completion_gate(cs: List<&2, Bool>) -> Decision:
  block_if(Bool.not(all_true(cs)))

# --- Checkpoints for user-defined Bend gates -------------------------------

# A user-written Bend law may install a runtime gate `def gate(c: G.Checkpoint)
# -> G.Decision`; the runtime calls it at every checkpoint of the matching kind.
type Checkpoint is Data:
  Write{resource: Nat}
  Retry{attempts: Nat}
  Claim{domains: List<&2, Nat>}
  Complete{checks: List<&2, Bool>}

# --- Law 5: spending limit (pre-action) -----------------------------------

# Block a payment whose amount (minor units) exceeds the cap.
def spend_gate(amount: Nat, cap: Nat) -> Decision:
  block_if(lt(cap, amount))

# --- Law 6: allowlists (pre-action) ---------------------------------------

# Allow an item (payee, capability) only if it is in the allowlist.
def allow_gate(+r: Nat, xs: +List<Nat>) -> Decision:
  block_if(Bool.not(elem(r, xs)))
