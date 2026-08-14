"""Every supported parser emits exact, closed-enum learning roles."""

from __future__ import annotations

from pathlib import Path

import pytest

from codemble.adapters.csharp_tree_sitter import CSharpAdapter
from codemble.adapters.go_tree_sitter import GoAdapter
from codemble.adapters.java_tree_sitter import JavaAdapter
from codemble.adapters.python_ast import PythonAstAdapter
from codemble.adapters.rust_tree_sitter import RustAdapter
from codemble.adapters.typescript_tree_sitter import JavaScriptTypeScriptAdapter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("language", "adapter", "fixture", "node_name", "rule_id"),
    (
        ("python", PythonAstAdapter(), "sampleproj", "main", "python.entrypoint.main"),
        ("go", GoAdapter(), "go_sample", "main", "go.entrypoint.main"),
        ("java", JavaAdapter(), "java_sample", "main", "java.entrypoint.main"),
        ("rust", RustAdapter(), "rust_sample", "main", "rust.entrypoint.main"),
        ("csharp", CSharpAdapter(), "csharp_sample", "Main", "csharp.entrypoint.main"),
    ),
)
def test_native_entrypoint_roles_cover_each_non_web_language(
    language: str,
    adapter: object,
    fixture: str,
    node_name: str,
    rule_id: str,
) -> None:
    graph = adapter.parse(FIXTURES / fixture)  # type: ignore[attr-defined]

    evidence = next(
        item
        for item in graph.role_evidence
        if item.role == "application-entry"
        and next(node for node in graph.nodes if node.id == item.node_id).name == node_name
    )
    owner = next(node for node in graph.nodes if node.id == evidence.node_id)

    assert owner.language == language
    assert evidence.rule_id == rule_id
    assert evidence.file == owner.file
    assert evidence.lineno == owner.lineno


def test_javascript_and_typescript_are_proven_independently(tmp_path: Path) -> None:
    (tmp_path / "main.js").write_text(
        "export function main() { return 1; }\nmain();\n",
        encoding="utf-8",
    )
    (tmp_path / "main.ts").write_text(
        "export function main(): number { return 1; }\nmain();\n",
        encoding="utf-8",
    )

    graph = JavaScriptTypeScriptAdapter().parse(tmp_path)
    roles = {
        next(node for node in graph.nodes if node.id == item.node_id).language: item.rule_id
        for item in graph.role_evidence
        if item.role == "application-entry"
        and next(node for node in graph.nodes if node.id == item.node_id).kind == "function"
    }

    assert roles == {
        "javascript": "javascript.entrypoint.main",
        "typescript": "typescript.entrypoint.main",
    }


def test_python_route_and_test_roles_keep_exact_parser_spans(tmp_path: Path) -> None:
    (tmp_path / "api.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/hello')\n"
        "def hello():\n"
        "    return 'hello'\n\n"
        "def test_hello():\n"
        "    assert hello() == 'hello'\n",
        encoding="utf-8",
    )

    graph = PythonAstAdapter().parse(tmp_path)
    by_role = {item.role: item for item in graph.role_evidence}

    assert by_role["route-handler"].rule_id == "python.decorator.get"
    assert by_role["route-handler"].file == "api.py"
    assert by_role["route-handler"].lineno == 3
    assert by_role["test"].rule_id == "python.test.function-name"
    assert by_role["test"].lineno == 7


def test_python_route_receiver_can_be_proven_in_an_enclosing_factory(tmp_path: Path) -> None:
    (tmp_path / "api.py").write_text(
        "from fastapi import FastAPI\n"
        "def create_app():\n"
        "    app = FastAPI()\n"
        "    @app.get('/hello')\n"
        "    def hello():\n"
        "        return 'hello'\n"
        "    return app\n",
        encoding="utf-8",
    )

    graph = PythonAstAdapter().parse(tmp_path)
    route = next(item for item in graph.role_evidence if item.role == "route-handler")

    assert route.rule_id == "python.decorator.get"
    assert route.file == "api.py"
    assert route.lineno == 4


def test_python_dotted_decorator_needs_a_framework_bound_receiver(tmp_path: Path) -> None:
    (tmp_path / "cache.py").write_text(
        "class Cache:\n"
        "    def get(self, key):\n"
        "        return lambda function: function\n\n"
        "cache = Cache()\n"
        "@cache.get('/hello')\n"
        "def hello():\n"
        "    return 'hello'\n",
        encoding="utf-8",
    )

    graph = PythonAstAdapter().parse(tmp_path)

    assert not [item for item in graph.role_evidence if item.role == "route-handler"]


def test_python_route_receiver_is_revoked_after_rebinding(tmp_path: Path) -> None:
    (tmp_path / "api.py").write_text(
        "from fastapi import FastAPI\n"
        "class Cache:\n"
        "    def get(self, key):\n"
        "        return lambda function: function\n\n"
        "app = FastAPI()\n"
        "app = Cache()\n"
        "@app.get('/hello')\n"
        "def hello():\n"
        "    return 'hello'\n",
        encoding="utf-8",
    )

    graph = PythonAstAdapter().parse(tmp_path)

    assert not [item for item in graph.role_evidence if item.role == "route-handler"]


def test_python_receiver_shadowing_inside_a_compound_statement_is_lexical(
    tmp_path: Path,
) -> None:
    (tmp_path / "api.py").write_text(
        "from fastapi import FastAPI\n"
        "class Cache:\n"
        "    def get(self, key):\n"
        "        return lambda function: function\n\n"
        "app = FastAPI()\n"
        "def register(flag):\n"
        "    if flag:\n"
        "        app = Cache()\n"
        "    @app.get('/hello')\n"
        "    def hello():\n"
        "        return 'hello'\n",
        encoding="utf-8",
    )

    graph = PythonAstAdapter().parse(tmp_path)

    assert not [item for item in graph.role_evidence if item.role == "route-handler"]


def test_javascript_cross_file_route_keeps_registration_and_declaration_separate(
    tmp_path: Path,
) -> None:
    (tmp_path / "handlers.js").write_text(
        "export function show() { return 'hello'; }\n",
        encoding="utf-8",
    )
    (tmp_path / "main.js").write_text(
        "import express from 'express';\n"
        "import { show } from './handlers.js';\n"
        "const app = express();\n"
        "app.get('/hello', show);\n"
        "app.listen(3000);\n",
        encoding="utf-8",
    )

    graph = JavaScriptTypeScriptAdapter().parse(tmp_path)
    route = next(item for item in graph.role_evidence if item.role == "route-handler")
    owner = next(node for node in graph.nodes if node.id == route.node_id)

    assert route.rule_id == "javascript.express.get"
    assert route.file == "main.js"
    assert route.lineno == 4
    assert owner.file == "handlers.js"
    assert owner.name == "show"


def test_javascript_route_receiver_requires_an_express_binding(tmp_path: Path) -> None:
    (tmp_path / "main.js").write_text(
        "function show() { return 'hello'; }\n"
        "const app = { get(path, handler) { return handler; } };\n"
        "app.get('/hello', show);\n",
        encoding="utf-8",
    )

    graph = JavaScriptTypeScriptAdapter().parse(tmp_path)

    assert not [item for item in graph.role_evidence if item.role == "route-handler"]


def test_javascript_route_receiver_respects_lexical_shadowing(tmp_path: Path) -> None:
    (tmp_path / "main.js").write_text(
        "import express from 'express';\n"
        "const app = express();\n"
        "function configure() {\n"
        "  const app = { get(path, handler) { return handler; } };\n"
        "  function show() { return 'hello'; }\n"
        "  app.get('/hello', show);\n"
        "}\n",
        encoding="utf-8",
    )

    graph = JavaScriptTypeScriptAdapter().parse(tmp_path)

    assert not [item for item in graph.role_evidence if item.role == "route-handler"]


def test_javascript_var_receiver_shadowing_is_hoisted_through_blocks(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.js").write_text(
        "import express from 'express';\n"
        "const app = express();\n"
        "function configure(flag) {\n"
        "  if (flag) {\n"
        "    var app = { get(path, handler) { return handler; } };\n"
        "  }\n"
        "  function show() { return 'hello'; }\n"
        "  app.get('/hello', show);\n"
        "}\n",
        encoding="utf-8",
    )

    graph = JavaScriptTypeScriptAdapter().parse(tmp_path)

    assert not [item for item in graph.role_evidence if item.role == "route-handler"]


@pytest.mark.parametrize(
    ("adapter", "file_name", "source"),
    (
        (
            JavaScriptTypeScriptAdapter(),
            "main.js",
            (
                "import express from 'express';\nconst app = express();\n"
                "function show() {}\napp.get('/x', show);\nfunction broken(\n"
            ),
        ),
        (GoAdapter(), "main.go", "package main\nfunc main() {}\nfunc broken(\n"),
        (
            JavaAdapter(),
            "App.java",
            "class App { public static void main(String[] args) {} void broken( }\n",
        ),
        (RustAdapter(), "main.rs", "fn main() {}\nfn broken(\n"),
        (CSharpAdapter(), "App.cs", "class App { static void Main() {} void Broken( }\n"),
    ),
)
def test_partial_tree_sitter_files_drop_roles_instead_of_failing_the_graph(
    tmp_path: Path,
    adapter: object,
    file_name: str,
    source: str,
) -> None:
    (tmp_path / file_name).write_text(source, encoding="utf-8")

    graph = adapter.parse(tmp_path)  # type: ignore[attr-defined]

    assert file_name in graph.partial_files
    assert all(item.file != file_name for item in graph.role_evidence)


def test_typescript_jsx_marks_the_owning_function_as_ui_renderer(tmp_path: Path) -> None:
    (tmp_path / "main.tsx").write_text(
        "export function App() {\n"
        "  return <main>Hello</main>;\n"
        "}\n"
        "createRoot(root).render(<App />);\n",
        encoding="utf-8",
    )

    graph = JavaScriptTypeScriptAdapter().parse(tmp_path)
    ui = next(item for item in graph.role_evidence if item.role == "ui-renderer")
    owner = next(node for node in graph.nodes if node.id == ui.node_id)

    assert ui.rule_id == "typescript.jsx.render"
    assert ui.lineno == 2
    assert owner.name == "App"


@pytest.mark.parametrize(
    ("adapter", "fixture", "owner_name", "rule_id", "line"),
    (
        (GoAdapter(), "go_sample", "TestMain", "go.test.function-name", 8),
        (JavaAdapter(), "java_sample", "startsUp", "java.junit.test", 7),
        (RustAdapter(), "rust_sample", "main_reports_failures", "rust.attribute.test", 17),
        (CSharpAdapter(), "csharp_sample", "SavesWithoutThrowing", "csharp.attribute.fact", 8),
    ),
)
def test_native_test_roles_keep_the_framework_observation(
    adapter: object,
    fixture: str,
    owner_name: str,
    rule_id: str,
    line: int,
) -> None:
    graph = adapter.parse(FIXTURES / fixture)  # type: ignore[attr-defined]
    evidence = next(
        item
        for item in graph.role_evidence
        if item.role == "test"
        and next(node for node in graph.nodes if node.id == item.node_id).name == owner_name
    )

    assert evidence.rule_id == rule_id
    assert evidence.lineno == line


@pytest.mark.parametrize(
    ("adapter", "file_name", "source", "owner_name", "rule_id", "line"),
    (
        (
            JavaAdapter(),
            "Api.java",
            (
                "import org.springframework.web.bind.annotation.GetMapping;\n"
                "class Api {\n  @GetMapping(\"/hello\")\n"
                "  String hello() { return \"hello\"; }\n}\n"
            ),
            "hello",
            "java.spring.getmapping",
            3,
        ),
        (
            RustAdapter(),
            "main.rs",
            (
                "use actix_web::get;\n#[get(\"/hello\")]\n"
                "fn hello() -> &'static str { \"hello\" }\nfn main() { hello(); }\n"
            ),
            "hello",
            "rust.attribute.get",
            2,
        ),
        (
            CSharpAdapter(),
            "Api.cs",
            (
                "using Microsoft.AspNetCore.Mvc;\n"
                "class Api {\n  [HttpGet(\"/hello\")]\n"
                "  public string Hello() { return \"hello\"; }\n}\n"
            ),
            "Hello",
            "csharp.aspnet.httpget",
            3,
        ),
    ),
)
def test_annotated_http_handlers_are_framework_roles(
    tmp_path: Path,
    adapter: object,
    file_name: str,
    source: str,
    owner_name: str,
    rule_id: str,
    line: int,
) -> None:
    (tmp_path / file_name).write_text(source, encoding="utf-8")

    graph = adapter.parse(tmp_path)  # type: ignore[attr-defined]
    evidence = next(item for item in graph.role_evidence if item.role == "route-handler")
    owner = next(node for node in graph.nodes if node.id == evidence.node_id)

    assert owner.name == owner_name
    assert evidence.rule_id == rule_id
    assert evidence.lineno == line


@pytest.mark.parametrize(
    ("adapter", "file_name", "source"),
    (
        (
            GoAdapter(),
            "main.go",
            (
                "package main\ntype fake struct{}\n"
                "func (fake) HandleFunc(string, func()) {}\n"
                "func show() {}\n"
                "func main() { var http fake; http.HandleFunc(\"/x\", show) }\n"
            ),
        ),
        (
            JavaAdapter(),
            "Api.java",
            (
                "@interface GetMapping { String value(); }\n"
                "class Api { @GetMapping(\"/x\") String hello() { return \"x\"; } }\n"
            ),
        ),
        (
            RustAdapter(),
            "main.rs",
            "#[get(\"/x\")]\nfn hello() {}\nfn main() {}\n",
        ),
        (
            CSharpAdapter(),
            "Api.cs",
            (
                "class HttpGetAttribute : System.Attribute {}\n"
                "class Api { [HttpGet] public string Hello() { return \"x\"; } }\n"
            ),
        ),
    ),
)
def test_framework_named_syntax_without_framework_provenance_is_not_a_route(
    tmp_path: Path,
    adapter: object,
    file_name: str,
    source: str,
) -> None:
    (tmp_path / file_name).write_text(source, encoding="utf-8")

    graph = adapter.parse(tmp_path)  # type: ignore[attr-defined]

    assert not [item for item in graph.role_evidence if item.role == "route-handler"]


@pytest.mark.parametrize(
    ("adapter", "file_name", "source"),
    (
        (
            JavaAdapter(),
            "Api.java",
            (
                "import fake.org.springframework.web.bind.annotation.GetMapping;\n"
                "class Api { @GetMapping(\"/x\") String hello() { return \"x\"; } }\n"
            ),
        ),
        (
            RustAdapter(),
            "main.rs",
            "use fake_actix_web::get;\n#[get(\"/x\")]\nfn hello() {}\n",
        ),
        (
            CSharpAdapter(),
            "Api.cs",
            (
                "using Evil.Microsoft.AspNetCore.Mvc.Compat;\n"
                "class Api { [HttpGet] public string Hello() { return \"x\"; } }\n"
            ),
        ),
    ),
)
def test_lookalike_framework_packages_do_not_prove_routes(
    tmp_path: Path,
    adapter: object,
    file_name: str,
    source: str,
) -> None:
    (tmp_path / file_name).write_text(source, encoding="utf-8")

    graph = adapter.parse(tmp_path)  # type: ignore[attr-defined]

    assert not [item for item in graph.role_evidence if item.role == "route-handler"]


@pytest.mark.parametrize(
    ("adapter", "file_name", "source"),
    (
        (
            JavaAdapter(),
            "Api.java",
            (
                "import org.springframework.web.bind.annotation.RestController;\n"
                "import fake.GetMapping;\n"
                "class Api { @GetMapping(\"/x\") String hello() { return \"x\"; } }\n"
            ),
        ),
        (
            RustAdapter(),
            "main.rs",
            "use actix_web::web;\nuse fake::get;\n#[get(\"/x\")]\nfn hello() {}\n",
        ),
    ),
)
def test_unrelated_framework_imports_do_not_authorize_named_route_syntax(
    tmp_path: Path,
    adapter: object,
    file_name: str,
    source: str,
) -> None:
    (tmp_path / file_name).write_text(source, encoding="utf-8")

    graph = adapter.parse(tmp_path)  # type: ignore[attr-defined]

    assert not [item for item in graph.role_evidence if item.role == "route-handler"]


@pytest.mark.parametrize(
    ("adapter", "file_name", "source"),
    (
        (
            JavaAdapter(),
            "Example.java",
            "@interface Test {}\nclass Example { @Test void helper() {} }\n",
        ),
        (
            CSharpAdapter(),
            "Example.cs",
            (
                "class FactAttribute : System.Attribute {}\n"
                "class Example { [Fact] public void Helper() {} }\n"
            ),
        ),
    ),
)
def test_framework_named_syntax_without_framework_provenance_is_not_a_test(
    tmp_path: Path,
    adapter: object,
    file_name: str,
    source: str,
) -> None:
    (tmp_path / file_name).write_text(source, encoding="utf-8")

    graph = adapter.parse(tmp_path)  # type: ignore[attr-defined]

    assert not [item for item in graph.role_evidence if item.role == "test"]


@pytest.mark.parametrize(
    ("adapter", "file_name", "source"),
    (
        (
            JavaAdapter(),
            "Example.java",
            "import evil.org.junit.Test;\nclass Example { @Test void helper() {} }\n",
        ),
        (
            CSharpAdapter(),
            "Example.cs",
            "using Evil.XunitCompat;\nclass Example { [Fact] public void Helper() {} }\n",
        ),
    ),
)
def test_lookalike_test_packages_do_not_prove_tests(
    tmp_path: Path,
    adapter: object,
    file_name: str,
    source: str,
) -> None:
    (tmp_path / file_name).write_text(source, encoding="utf-8")

    graph = adapter.parse(tmp_path)  # type: ignore[attr-defined]

    assert not [item for item in graph.role_evidence if item.role == "test"]


@pytest.mark.parametrize(
    "source",
    (
        (
            "using X = Xunit;\n"
            "class FactAttribute : System.Attribute {}\n"
            "class Example { [Fact] public void Helper() {} }\n"
        ),
        (
            "using Xunit;\n"
            "class FactAttribute : System.Attribute {}\n"
            "class Example { [Fact] public void Helper() {} }\n"
        ),
    ),
)
def test_csharp_namespace_or_alias_does_not_override_a_local_test_attribute(
    tmp_path: Path,
    source: str,
) -> None:
    (tmp_path / "Example.cs").write_text(source, encoding="utf-8")

    graph = CSharpAdapter().parse(tmp_path)

    assert not [item for item in graph.role_evidence if item.role == "test"]


def test_java_unrelated_junit_import_does_not_authorize_local_test_annotation(
    tmp_path: Path,
) -> None:
    (tmp_path / "Example.java").write_text(
        "import org.junit.Assert;\n"
        "@interface Test {}\n"
        "class Example { @Test void helper() {} }\n",
        encoding="utf-8",
    )

    graph = JavaAdapter().parse(tmp_path)

    assert not [item for item in graph.role_evidence if item.role == "test"]


@pytest.mark.parametrize(
    "source",
    (
        (
            "import org.junit.Test;\n"
            "class Example { @interface Test {} @Test void helper() {} }\n"
        ),
        (
            "import org.springframework.web.bind.annotation.GetMapping;\n"
            "class Api {\n"
            "  @interface GetMapping { String value(); }\n"
            "  @GetMapping(\"/x\") String hello() { return \"x\"; }\n"
            "}\n"
        ),
    ),
)
def test_java_project_annotation_shadows_imported_framework_type(
    tmp_path: Path,
    source: str,
) -> None:
    (tmp_path / "Example.java").write_text(source, encoding="utf-8")

    graph = JavaAdapter().parse(tmp_path)

    assert not [
        item
        for item in graph.role_evidence
        if item.role in {"test", "route-handler"}
    ]


def test_csharp_framework_namespace_does_not_override_local_route_attribute(
    tmp_path: Path,
) -> None:
    (tmp_path / "Api.cs").write_text(
        "using Microsoft.AspNetCore.Mvc;\n"
        "class HttpGetAttribute : System.Attribute {}\n"
        "class Api { [HttpGet] public string Hello() { return \"x\"; } }\n",
        encoding="utf-8",
    )

    graph = CSharpAdapter().parse(tmp_path)

    assert not [item for item in graph.role_evidence if item.role == "route-handler"]


def test_go_net_http_registration_resolves_a_cross_package_handler(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module example.com/demo\n", encoding="utf-8")
    handler_dir = tmp_path / "internal" / "handlers"
    handler_dir.mkdir(parents=True)
    (handler_dir / "handlers.go").write_text(
        "package handlers\nfunc Show() {}\n",
        encoding="utf-8",
    )
    command_dir = tmp_path / "cmd" / "app"
    command_dir.mkdir(parents=True)
    (command_dir / "main.go").write_text(
        "package main\n"
        "import (\n"
        "  \"net/http\"\n"
        "  \"example.com/demo/internal/handlers\"\n"
        ")\n"
        "func main() {\n"
        "  http.HandleFunc(\"/hello\", handlers.Show)\n"
        "}\n",
        encoding="utf-8",
    )

    graph = GoAdapter().parse(tmp_path)
    evidence = next(item for item in graph.role_evidence if item.role == "route-handler")
    owner = next(node for node in graph.nodes if node.id == evidence.node_id)

    assert evidence.rule_id == "go.net-http.handlefunc"
    assert evidence.file == "cmd/app/main.go"
    assert evidence.lineno == 7
    assert owner.file == "internal/handlers/handlers.go"
    assert owner.name == "Show"
