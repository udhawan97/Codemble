"""Run a deterministic TLS share viewer for disposable browser acceptance."""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import uvicorn

from codemble.adapters.python_ast import PythonAstAdapter
from codemble.share import (
    InMemoryShareStorage,
    ShareArtifact,
    ShareDelivery,
    SharePolicy,
    StructuredShareLifecycleLog,
    create_share_delivery_app,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--cert", required=True, type=Path)
    parser.add_argument("--key", required=True, type=Path)
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    created_at = datetime.now(UTC)
    artifact = ShareArtifact.from_graph(
        PythonAstAdapter().parse(Path("tests/fixtures/sampleproj")),
        SharePolicy(
            expires_at=created_at + timedelta(days=1),
            include_labels=True,
            include_understanding=True,
        ),
        created_at,
    )
    entropy = iter((bytes([1]) * 32, bytes([2]) * 32))
    delivery = ShareDelivery(
        InMemoryShareStorage(),
        StructuredShareLifecycleLog(),
        clock=lambda: datetime.now(UTC),
        entropy=lambda size: next(entropy),
    )
    delivery.create(artifact)
    app = create_share_delivery_app(
        delivery,
        allowed_hosts=(f"127.0.0.1:{arguments.port}",),
    )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=arguments.port,
        ssl_certfile=str(arguments.cert),
        ssl_keyfile=str(arguments.key),
        access_log=True,
    )


if __name__ == "__main__":
    main()
