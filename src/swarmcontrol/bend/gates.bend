# Command-line driver for the proven gates in governor.bend: compiled to a native program that the governor calls
# (the Python runtime). One call per check:  gates <gate> <args...>   prints allow | block | escalate | error.
# Lists are comma-separated Nats ("-" is the empty list); completion checks are 1 (passed) or 0 (failed).
import Base
import ./governor.bend as G

def show(d: G.Decision) -> String:
  match d:
    case G.Allow{}:
      "allow"
    case G.Block{}:
      "block"
    case G.Escalate{}:
      "escalate"

def when(b: Bool, yes: String, no: String) -> String:
  match b:
    case True{}:
      yes
    case False{}:
      no

def nums.tail(n: Nat, r: Maybe<&2, List<&2, Nat>>) -> Maybe<&2, List<&2, Nat>>:
  match r:
    case None{}:
      None{}
    case Some{rest}:
      Some{Con{n, rest}}

def nums.cons(m: Maybe<&2, Nat>, r: Maybe<&2, List<&2, Nat>>) -> Maybe<&2, List<&2, Nat>>:
  match m:
    case None{}:
      None{}
    case Some{n}:
      nums.tail(n, r)

def nums(xs: List<&2, String>) -> Maybe<&2, List<&2, Nat>>:
  match xs:
    case Nil{}:
      Some{Nil{}}
    case Con{h, t}:
      nums.cons(Nat.read(h), nums(t))

def list.go(empty: Bool, s: String) -> Maybe<&2, List<&2, Nat>>:
  match empty:
    case True{}:
      Some{Nil{}}
    case False{}:
      nums(String.split(s, ','))

def list(+s: String) -> Maybe<&2, List<&2, Nat>>:
  list.go(String.eq(s, "-"), s)

def bools(xs: List<&2, Nat>) -> List<&2, Bool>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{h, t}:
      Con{Nat.is_eq(h, 1n), bools(t)}

def n1.go(m: Maybe<&2, Nat>, f: Nat -> String) -> String:
  match m:
    case None{}:
      "error"
    case Some{x}:
      f(x)

def n1(a: String, f: Nat -> String) -> String:
  n1.go(Nat.read(a), f)

def l1.go(m: Maybe<&2, List<&2, Nat>>, f: List<&2, Nat> -> String) -> String:
  match m:
    case None{}:
      "error"
    case Some{xs}:
      f(xs)

def l1(a: String, f: List<&2, Nat> -> String) -> String:
  l1.go(list(a), f)

def run.two(+gate: String, +a: String, +b: String) -> String:
  when(String.eq(gate, "write_gate"), n1(a, r => l1(b, ps => show(G.write_gate(r, ps)))),
  when(String.eq(gate, "allow_gate"), n1(a, r => l1(b, xs => show(G.allow_gate(r, xs)))),
  when(String.eq(gate, "evidence_gate"), n1(a, m => l1(b, ds => show(G.evidence_gate(m, ds)))),
  when(String.eq(gate, "retry_gate"), n1(a, x => n1(b, m => show(G.retry_gate(x, m)))),
  when(String.eq(gate, "spend_gate"), n1(a, x => n1(b, c => show(G.spend_gate(x, c)))),
  "error")))))

def run.one(+gate: String, +a: String) -> String:
  when(String.eq(gate, "completion_gate"), l1(a, xs => show(G.completion_gate(bools(xs)))), "error")

def run.args(+gate: String, +a: String, rest: List<&2, String>) -> String:
  match rest:
    case Nil{}:
      run.one(gate, a)
    case Con{b, more}:
      run.two(gate, a, b)

def run(+gate: String, args: List<&2, String>) -> String:
  match args:
    case Nil{}:
      "error"
    case Con{a, rest}:
      run.args(gate, a, rest)

def answer.gate(rest: List<&2, String>) -> String:
  match rest:
    case Nil{}:
      "error"
    case Con{gate, args}:
      run(gate, args)

def answer(argv: List<&2, String>) -> String:
  match argv:
    case Nil{}:
      "error"
    case Con{prog, rest}:
      answer.gate(rest)

def reusable(xs: List<&1, String>) -> List<&2, String>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{h, t}:
      Con{h, reusable(t)}

def main() -> IO(Unit):
  do IO<Unit>:
    argv : List<&1, String> <- IO.args()
    IO.print(answer(reusable(argv)))
