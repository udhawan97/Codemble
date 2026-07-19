from collections.abc import AsyncIterable, Iterable


def traced(function):
    return function


@traced
async def collect(values: list[int]) -> list[int]:
    cleaned = [value for value in values if value > 0]
    mapping = {value: str(value) for value in cleaned}
    async for item in AsyncIterable():
        await item
    with open("values.txt") as handle:
        handle.read()
    try:
        return cleaned
    except ValueError as error:
        raise RuntimeError from error


def stream(values: Iterable[int]):
    yield from values


def expression(values: Iterable[int]):
    return (value for value in values)


class Example:
    size: int = 0

    def __len__(self) -> int:
        return self.size
