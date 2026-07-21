"""Guard the tree-sitter core/grammar pairing that the parser segfaults without.

tree-sitter 0.26.0 is ABI-incompatible with the newest published grammar wheels
(``tree-sitter-javascript`` 0.25.0, ``tree-sitter-typescript`` 0.23.2 — the only
ones that exist). Paired with 0.26.0 the parser dies with SIGSEGV inside
``node_get_named_children`` partway through a real project, taking the whole
process — and, in the app, the local server — down with it.

A behavioural test cannot catch this: a small snippet parses and walks fine on
0.26.0, and every fixture in this suite is small. It only trips on a corpus of
real size, which is exactly why it reached a release. So the guard asserts the
resolved version instead of the behaviour.

Raise the ceiling only after verifying a grammar release against the newer core
on a project of real size.
"""

from __future__ import annotations

import importlib.metadata as metadata


def _version_tuple(distribution: str) -> tuple[int, ...]:
    raw = metadata.version(distribution)
    return tuple(int(part) for part in raw.split(".")[:3] if part.isdigit())


def test_tree_sitter_core_stays_below_the_segfaulting_release() -> None:
    assert _version_tuple("tree-sitter") < (0, 26), (
        "tree-sitter >= 0.26 segfaults against the published grammar wheels; "
        "pyproject pins <0.26 deliberately."
    )


def test_tree_sitter_core_is_new_enough_for_the_grammars() -> None:
    assert _version_tuple("tree-sitter") >= (0, 25), (
        "the JS/TS adapter is written against the 0.25 Language/Parser API."
    )


def test_grammar_wheels_are_the_pinned_pairing() -> None:
    assert _version_tuple("tree-sitter-javascript") >= (0, 25)
    assert _version_tuple("tree-sitter-typescript") >= (0, 23, 2)
