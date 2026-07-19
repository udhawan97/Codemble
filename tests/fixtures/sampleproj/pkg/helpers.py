from pkg.util import normalize


def log(value: str) -> None:
    normalized = normalize(value)
    print(normalized)
