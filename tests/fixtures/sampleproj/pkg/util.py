def greet(name: str) -> str:
    return normalize(name)


def normalize(value: str) -> str:
    return value.strip()


def duplicate() -> str:
    return "pkg"
