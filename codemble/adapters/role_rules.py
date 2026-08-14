"""Shared constructors for parser-owned learning roles."""

from __future__ import annotations

from collections.abc import Iterable

from codemble.adapters.base import Node, RoleEvidence


def native_entrypoint_roles(
    nodes: tuple[Node, ...] | list[Node],
) -> tuple[RoleEvidence, ...]:
    """Persist native ``main`` decisions already proven by an adapter."""

    roles = {
        RoleEvidence(
            node_id=node.id,
            role="application-entry",
            rule_id=f"{node.language}.entrypoint.main",
            file=node.file,
            lineno=node.lineno,
            end_lineno=node.lineno,
        )
        for node in nodes
        if not node.partial
        and node.kind == "function"
        and node.name.casefold() == "main"
        and node.entrypoint_rank in {0, 1}
    }
    return tuple(
        sorted(roles, key=lambda item: (item.file, item.lineno, item.node_id))
    )


def roles_from_complete_files(
    roles: Iterable[RoleEvidence],
    nodes: tuple[Node, ...] | list[Node],
    partial_files: Iterable[str],
) -> tuple[RoleEvidence, ...]:
    """Drop observations a parser explicitly marked incomplete.

    Finalization still rejects hand-built invalid graphs. Adapters call this
    before finalization because a tree-sitter recovery can retain an earlier
    valid-looking annotation in a file whose later syntax error makes the whole
    file unsafe as role evidence.
    """

    partial = frozenset(partial_files)
    node_by_id = {node.id: node for node in nodes}
    complete = {
        evidence
        for evidence in roles
        if evidence.file not in partial
        and (
            (node := node_by_id.get(evidence.node_id)) is None
            or (not node.partial and node.file not in partial)
        )
    }
    return tuple(
        sorted(
            complete,
            key=lambda item: (
                item.file,
                item.lineno,
                item.role,
                item.rule_id,
                item.node_id,
            ),
        )
    )


__all__ = ["native_entrypoint_roles", "roles_from_complete_files"]
