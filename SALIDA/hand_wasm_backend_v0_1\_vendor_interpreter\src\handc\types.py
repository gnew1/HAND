from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

# ----- Type representation (normative, v0.1) -----
class Type:
    def __str__(self) -> str:
        raise NotImplementedError

@dataclass(frozen=True)
class Prim(Type):
    name: str  # Int, Float, Bool, Text, Null
    def __str__(self) -> str:
        return self.name

@dataclass(frozen=True)
class AnyT(Type):
    def __str__(self) -> str:
        return "Any"

@dataclass(frozen=True)
class NeverT(Type):
    def __str__(self) -> str:
        return "Never"

@dataclass(frozen=True)
class OptionalT(Type):
    inner: Type
    def __str__(self) -> str:
        return f"{self.inner}?"

@dataclass(frozen=True)
class ListT(Type):
    elem: Type
    def __str__(self) -> str:
        return f"List[{self.elem}]"

@dataclass(frozen=True)
class MapT(Type):
    key: Type
    val: Type
    def __str__(self) -> str:
        return f"Map[{self.key},{self.val}]"

@dataclass(frozen=True)
class RecordT(Type):
    name: str
    def __str__(self) -> str:
        return self.name

@dataclass(frozen=True)
class ResultT(Type):
    ok: Type
    err: Type
    def __str__(self) -> str:
        return f"Result[{self.ok},{self.err}]"

# Singletons
INT=Prim("Int")
FLOAT=Prim("Float")
BOOL=Prim("Bool")
TEXT=Prim("Text")
NULL=Prim("Null")
ANY=AnyT()
NEVER=NeverT()

def is_optional(t: Type) -> bool:
    return isinstance(t, OptionalT)

def strip_optional(t: Type) -> Type:
    return t.inner if isinstance(t, OptionalT) else t

def make_optional(t: Type) -> Type:
    return t if isinstance(t, OptionalT) else OptionalT(t)

def same(a: Type, b: Type) -> bool:
    return a == b

def assignable(src: Type, dst: Type) -> bool:
    # Any rules
    if isinstance(dst, AnyT) or isinstance(src, AnyT):
        return True
    # Never is assignable to anything
    if isinstance(src, NeverT):
        return True
    # Exact match
    if src == dst:
        return True
    # Null into Optional[T]
    if src == NULL and isinstance(dst, OptionalT):
        return True
    # T into Optional[T]
    if isinstance(dst, OptionalT) and assignable(src, dst.inner):
        return True
    # Optional[T] NOT into T
    return False

def join(a: Type, b: Type) -> Type:
    """Least upper bound-ish for v0.1: used by if/else merges."""
    if a == b:
        return a
    if isinstance(a, AnyT) or isinstance(b, AnyT):
        return ANY
    if a == NULL:
        return make_optional(b)
    if b == NULL:
        return make_optional(a)
    if isinstance(a, OptionalT) and not isinstance(b, OptionalT):
        return OptionalT(join(a.inner, b))
    if isinstance(b, OptionalT) and not isinstance(a, OptionalT):
        return OptionalT(join(a, b.inner))
    # primitive widening: Int + Float => Float (only used in arithmetic)
    return ANY
