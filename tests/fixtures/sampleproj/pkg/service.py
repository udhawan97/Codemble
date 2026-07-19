from shared import duplicate

from .util import normalize


class Service:
    def run(self) -> str:
        value = normalize(" ready ")
        duplicate()
        return self.finish(value)

    def finish(self, value: str) -> str:
        return str(len(value))
