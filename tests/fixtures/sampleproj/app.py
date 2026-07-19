import json

from pkg import helpers
from pkg.service import Service
from pkg.util import greet


def main() -> None:
    service = Service()
    message = greet("world")
    helpers.log(message)
    print(json.dumps(message))
    service.run()


if __name__ == "__main__":
    main()
