"""Deterministic, keyed randomness. Every draw is keyed by (seed, agent, purpose), never by global call order, so a
baseline and a governed run with the same seed see identical fault schedules even though their executions diverge.
Bit-for-bit identical to the TypeScript version (FNV-1a key hash, mulberry32 stream)."""

from __future__ import annotations

from typing import Sequence, TypeVar

T = TypeVar("T")
M = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    return (a * b) & M


def _hash(s: str) -> int:
    h = 2166136261
    for unit in s.encode("utf-16-le")[::2]:  # keys are ASCII: one UTF-16 code unit per character
        h = _imul(h ^ unit, 16777619)
    return h


def _key(x) -> str:
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


class Rng:
    def __init__(self, seed: int, *key) -> None:
        self._a = _hash("|".join([_key(seed), "|".join(_key(k) for k in key)]))

    def float(self) -> float:
        self._a = (self._a + 0x6D2B79F5) & M
        t = self._a
        t = _imul(t ^ (t >> 15), t | 1)
        t ^= (t + _imul(t ^ (t >> 7), t | 61)) & M
        return ((t ^ (t >> 14)) & M) / 4294967296

    def int(self, lo: int, hi: int) -> int:
        return lo + int(self.float() * (hi - lo + 1))

    def chance(self, p: float) -> bool:
        return self.float() < p

    def pick(self, xs: Sequence[T]) -> T:
        return xs[int(self.float() * len(xs))]

    def weighted(self, weights: dict[str, float]) -> str | None:
        entries = [(k, w) for k, w in weights.items() if w > 0]
        total = sum(w for _, w in entries)
        if total <= 0:
            return None
        r = self.float() * total
        for k, w in entries:
            r -= w
            if r <= 0:
                return k
        return entries[-1][0]

    def shuffle(self, xs: list[T]) -> list[T]:
        a = list(xs)
        for i in range(len(a) - 1, 0, -1):
            j = int(self.float() * (i + 1))
            a[i], a[j] = a[j], a[i]
        return a
