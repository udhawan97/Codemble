def helper() -> int:
    return 1


def caller() -> int:
    total = helper()
    total += helper()
    total += helper()
    return total
