# Proofs of every law in LAWS.bend. Checked by `bend PROOF.bend`.
import Base
import ./governor.bend as G
import ./LAWS.bend as L

# --- Law 1 -----------------------------------------------------------------

def L.protected_write_blocked(r, ps, e):
  %Equal.sym(Bool, G.elem(r, ps), True{}, e) : {G.block_if(_) == G.Block{} : G.Decision}
  {==}

def L.unprotected_write_allowed(r, ps, e):
  %Equal.sym(Bool, G.elem(r, ps), False{}, e) : {G.block_if(_) == G.Allow{} : G.Decision}
  {==}

# --- Law 2 -----------------------------------------------------------------

law lt_add_self:
  for m: Nat
  for k: Nat
  {G.lt(Nat.add(m, k), m) == False{} : Bool}

def lt_add_self(m, k):
  match m k:
    case 0n 0n:
      {==}
    case 0n 1n+q:
      {==}
    case 1n+p k:
      lt_add_self(p, k)

def L.retry_budget_escalates(max, k):
  %Equal.sym(Bool, G.lt(Nat.add(max, k), max), False{}, lt_add_self(max, k)) : {G.escalate_unless(_) == G.Escalate{} : G.Decision}
  {==}

# --- Law 3 -----------------------------------------------------------------

law is_eq_refl:
  for n: Nat
  {Nat.is_eq(n, n) == True{} : Bool}

def is_eq_refl(n):
  match n:
    case 0n:
      {==}
    case 1n+p:
      is_eq_refl(p)

law elem_replicate:
  for d: Nat
  for n: Nat
  {G.elem(d, List.replicate(Nat, 1n+n, d)) == True{} : Bool}

def elem_replicate(d, n):
  %Equal.sym(Bool, Nat.is_eq(d, d), True{}, is_eq_refl(d)) : {Bool.or(_, G.elem(d, List.replicate(Nat, n, d))) == True{} : Bool}
  {==}

# (a typed def rather than law+def so its arguments can be marked reusable)
def distinct_replicate(+d: Nat, +n: Nat) -> {G.distinct(List.replicate(Nat, 1n+n, d)) == 1n : Nat}:
  match n:
    case 0n:
      {==}
    case 1n+p:
      %Equal.sym(Bool, G.elem(d, List.replicate(Nat, 1n+p, d)), True{}, elem_replicate(d, p)) : {G.distinct.step(G.distinct(List.replicate(Nat, 1n+p, d)), _) == 1n : Nat}
      distinct_replicate(d, p)

def L.single_domain_insufficient(d, n, k):
  %Equal.sym(Nat, G.distinct(List.replicate(Nat, 1n+n, d)), 1n, distinct_replicate(d, n)) : {G.block_if(G.lt(_, 2n+k)) == G.Block{} : G.Decision}
  {==}

# --- Law 4 -----------------------------------------------------------------

law all_true_with_false:
  for pre: List<&2, Bool>
  for post: List<&2, Bool>
  {G.all_true(List.append(&2, Bool, pre, False{} <> post)) == False{} : Bool}

def all_true_with_false(pre, post):
  match pre:
    case Nil{}:
      {==}
    case Con{h, t}:
      match h:
        case True{}:
          all_true_with_false(t, post)
        case False{}:
          {==}

def L.failed_check_blocks_completion(pre, post):
  %Equal.sym(Bool, G.all_true(List.append(&2, Bool, pre, False{} <> post)), False{}, all_true_with_false(pre, post)) : {G.block_if(Bool.not(_)) == G.Block{} : G.Decision}
  {==}

# --- Law 5 -----------------------------------------------------------------

law lt_below_add_succ:
  for m: Nat
  for k: Nat
  {G.lt(m, Nat.add(m, 1n+k)) == True{} : Bool}

def lt_below_add_succ(m, k):
  match m:
    case 0n:
      {==}
    case 1n+p:
      lt_below_add_succ(p, k)

def L.over_cap_blocked(cap, k):
  %Equal.sym(Bool, G.lt(cap, Nat.add(cap, 1n+k)), True{}, lt_below_add_succ(cap, k)) : {G.block_if(_) == G.Block{} : G.Decision}
  {==}

def L.within_cap_allowed(amount, k):
  %Equal.sym(Bool, G.lt(Nat.add(amount, k), amount), False{}, lt_add_self(amount, k)) : {G.block_if(_) == G.Allow{} : G.Decision}
  {==}

# --- Law 6 -----------------------------------------------------------------

def L.unlisted_blocked(r, xs, e):
  %Equal.sym(Bool, G.elem(r, xs), False{}, e) : {G.block_if(Bool.not(_)) == G.Block{} : G.Decision}
  {==}

def L.listed_allowed(r, xs, e):
  %Equal.sym(Bool, G.elem(r, xs), True{}, e) : {G.block_if(Bool.not(_)) == G.Allow{} : G.Decision}
  {==}
