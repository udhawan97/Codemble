"""Ruby and PHP keep the same evidence boundary as the established adapters."""

from __future__ import annotations

from pathlib import Path

from codemble.adapters.php_tree_sitter import PHPAdapter
from codemble.adapters.ruby_tree_sitter import RubyAdapter
from codemble.lens import lens_notes

FIXTURES = Path(__file__).parent / "fixtures"


def test_ruby_maps_nested_structure_and_never_overstates_dynamic_dispatch() -> None:
    graph = RubyAdapter().parse(FIXTURES / "ruby_sample")

    assert graph.partial_files == ("lib/broken.rb",)
    assert graph.selected_entrypoint == "ruby:bin/atlas.rb"
    assert {
        node.id
        for node in graph.nodes
        if node.kind != "module"
    } >= {
        "ruby:lib/atlas.rb::Atlas.Ship",
        "ruby:lib/atlas.rb::Atlas.Ship.launch",
        "ruby:lib/atlas.rb::Atlas.Ship.prime",
        "ruby:lib/atlas.rb::Atlas.Ship#land",
        "ruby:lib/atlas/navigation.rb::Atlas.Navigator.plot",
    }
    assert not any(
        node.file == "lib/broken.rb" and node.kind != "module" for node in graph.nodes
    )
    launch_edges = [
        edge
        for edge in graph.edges
        if edge.src == "ruby:lib/atlas.rb::Atlas.Ship.launch"
    ]
    assert any(
        edge.dst == "ruby:lib/atlas/navigation.rb::Atlas.Navigator.plot"
        for edge in launch_edges
    )
    assert any(
        edge.dst == "ruby:lib/atlas.rb::Atlas.Ship.prime"
        and edge.lineno == 6
        for edge in launch_edges
    )
    assert all(not edge.certain for edge in launch_edges)
    assert any(
        edge.dst == "external:puts"
        and edge.external
        and edge.lineno == 8
        for edge in launch_edges
    )
    assert any(
        evidence.node_id == "ruby:bin/atlas.rb"
        and evidence.rule_id == "ruby.entrypoint.program-name"
        for evidence in graph.role_evidence
    )


def test_ruby_idioms_have_both_easy_and_expert_evidence_captions() -> None:
    graph = RubyAdapter().parse(FIXTURES / "ruby_sample")
    annotations = [
        annotation
        for annotation in graph.concept_annotations
        if annotation.node_id == "ruby:lib/atlas.rb::Atlas.Ship.launch"
    ]

    notes = lens_notes("ruby", annotations)

    assert {note["concept"] for note in notes} >= {
        "block",
        "safe-navigation",
        "singleton-method",
        "string-interpolation",
    }
    assert all(set(note["explanations"]) == {"easy", "expert"} for note in notes)


def test_php_uses_composer_entrypoint_and_resolves_only_parser_evidenced_targets() -> None:
    graph = PHPAdapter().parse(FIXTURES / "php_sample")

    assert graph.partial_files == ("src/Broken.php",)
    assert graph.selected_entrypoint == "php:bin/atlas.php"
    assert {
        node.id
        for node in graph.nodes
        if node.kind != "module"
    } >= {
        "php:src/Navigator.php::App.Navigator",
        "php:src/Navigator.php::App.Navigator.plot",
        "php:src/Ship.php::App.Ship",
        "php:src/Ship.php::App.Ship.land",
        "php:src/Ship.php::App.Ship.dock",
    }
    assert not any(
        node.file == "src/Broken.php" and node.kind != "module" for node in graph.nodes
    )
    land_edges = [
        edge
        for edge in graph.edges
        if edge.src == "php:src/Ship.php::App.Ship.land"
    ]
    assert {edge.dst for edge in land_edges} >= {
        "php:src/Navigator.php::App.Navigator.plot",
        "php:src/Ship.php::App.Ship.dock",
    }
    assert all(not edge.certain for edge in land_edges)
    assert any(
        edge.src == "php:src/Ship.php"
        and edge.dst == "php:src/Navigator.php"
        and edge.kind == "import"
        and edge.certain
        for edge in graph.edges
    )
    assert any(
        edge.src == "php:bin/atlas.php"
        and edge.dst == "external:$ship->land"
        and not edge.certain
        and edge.external
        for edge in graph.edges
    )
    assert any(
        edge.src == "php:src/Ship.php::App.Ship.land"
        and edge.dst == "external:result?->manifest"
        and not edge.certain
        and edge.external
        for edge in graph.edges
    )


def test_php_modern_syntax_has_both_easy_and_expert_evidence_captions() -> None:
    graph = PHPAdapter().parse(FIXTURES / "php_sample")
    annotations = [
        annotation
        for annotation in graph.concept_annotations
        if annotation.language == "php"
    ]

    notes = lens_notes("php", annotations)

    assert {note["concept"] for note in notes} >= {
        "attribute",
        "match-expression",
        "nullsafe-access",
        "union-type",
    }
    assert all(set(note["explanations"]) == {"easy", "expert"} for note in notes)


def test_ruby_and_php_graphs_are_byte_identical_across_runs() -> None:
    for fixture, adapter in (
        ("ruby_sample", RubyAdapter()),
        ("php_sample", PHPAdapter()),
    ):
        first = adapter.parse(FIXTURES / fixture).to_json()
        second = adapter.parse(FIXTURES / fixture).to_json()
        assert first == second


def test_php_namespaces_are_owned_per_declaration(tmp_path: Path) -> None:
    (tmp_path / "braced.php").write_text(
        """<?php
namespace One { class A {} function alpha() {} }
namespace Two { class B {} function beta() {} }
""",
        encoding="utf-8",
    )
    (tmp_path / "semicolon.php").write_text(
        """<?php
namespace Three; class C {} function gamma() {}
namespace Four; class D {} function delta() {}
""",
        encoding="utf-8",
    )

    graph = PHPAdapter().parse(tmp_path)
    ids = {node.id for node in graph.nodes}

    assert {
        "php:braced.php::One.A",
        "php:braced.php::One.alpha",
        "php:braced.php::Two.B",
        "php:braced.php::Two.beta",
        "php:semicolon.php::Three.C",
        "php:semicolon.php::Three.gamma",
        "php:semicolon.php::Four.D",
        "php:semicolon.php::Four.delta",
    } <= ids
    assert "php:braced.php::One.B" not in ids
    assert "php:semicolon.php::Three.D" not in ids


def test_php_preserves_absolute_relative_and_grouped_names(tmp_path: Path) -> None:
    (tmp_path / "names.php").write_text(
        """<?php
namespace Vendor { class RootThing {} }
namespace Vendor\\Pack {
  class Thing { public static function run() {} }
  class Other { public static function go() {} }
}
namespace App {
  use Vendor\\Pack\\{Thing, Other as Elsewhere};
  class LocalClass {}
  function local() {}
  function voyage() {
    new \\Vendor\\RootThing();
    new namespace\\LocalClass();
    namespace\\local();
    Thing::run();
    Elsewhere::go();
  }
}
""",
        encoding="utf-8",
    )

    graph = PHPAdapter().parse(tmp_path)
    voyage = "php:names.php::App.voyage"
    targets = {edge.dst for edge in graph.edges if edge.src == voyage}
    imports = {
        edge.dst
        for edge in graph.edges
        if edge.src == "php:names.php" and edge.kind == "import"
    }

    assert targets >= {
        "php:names.php::Vendor.RootThing",
        "php:names.php::App.LocalClass",
        "php:names.php::App.local",
        "php:names.php::Vendor.Pack.Thing.run",
        "php:names.php::Vendor.Pack.Other.go",
    }
    assert imports >= {
        "php:names.php::Vendor.Pack.Thing",
        "php:names.php::Vendor.Pack.Other",
    }
    assert not any(target.startswith("external:App\\Vendor") for target in targets)
    assert not any(target in {"external:Thing", "external:Other"} for target in targets)


def test_ruby_singleton_class_and_bare_send_stay_possible(tmp_path: Path) -> None:
    (tmp_path / "widget.rb").write_text(
        """class Widget
  class << self
    def build
      helper
      explicit()
      local = 1
      local
    end
    def helper
    end
  end
end
""",
        encoding="utf-8",
    )

    graph = RubyAdapter().parse(tmp_path)
    ids = {node.id for node in graph.nodes}
    edges = [edge for edge in graph.edges if edge.src == "ruby:widget.rb::Widget.build"]

    assert "ruby:widget.rb::Widget.build" in ids
    assert "ruby:widget.rb::Widget.helper" in ids
    assert "ruby:widget.rb::Widget#build" not in ids
    assert any(edge.dst == "ruby:widget.rb::Widget.helper" for edge in edges)
    assert any(edge.dst == "external:explicit" for edge in edges)
    assert all(not edge.certain for edge in edges)
    assert not any(edge.dst == "external:local" for edge in edges)


def test_ruby_program_name_role_requires_top_level_equality(tmp_path: Path) -> None:
    (tmp_path / "good.rb").write_text(
        "if __FILE__ == $PROGRAM_NAME\n  launch\nend\n",
        encoding="utf-8",
    )
    (tmp_path / "inequality.rb").write_text(
        "if $PROGRAM_NAME != __FILE__\n  do_not_launch\nend\n",
        encoding="utf-8",
    )
    (tmp_path / "nested.rb").write_text(
        "def helper\n  if $PROGRAM_NAME == __FILE__\n    do_not_launch\n  end\nend\n",
        encoding="utf-8",
    )

    graph = RubyAdapter().parse(tmp_path)

    assert graph.selected_entrypoint == "ruby:good.rb"
    assert {evidence.node_id for evidence in graph.role_evidence} == {"ruby:good.rb"}
    assert next(node for node in graph.nodes if node.id == "ruby:inequality.rb").entrypoint_rank is None
    assert next(node for node in graph.nodes if node.id == "ruby:nested.rb").entrypoint_rank is None
