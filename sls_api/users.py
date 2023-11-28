class Users:
    pass


class User:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if k.startswith("_"):
                continue
            setattr(self, k, v)
        self.sources = {}

    def can_read(self, source: str) -> bool:
        return source in self.sources

    def can_readwrite(self, source: str) -> bool:
        return (
            self.can_read(source)
            and self.sources.get(source, {}).get("accessControl", "") == "readwrite"
        )

    def is_admin(self) -> bool:
        return self.name == "admin" or "admin" in self.groups

    def set_sources(self, sources: dict):
        self.sources = sources
