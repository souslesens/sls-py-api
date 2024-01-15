from dataclasses import dataclass, field


class Users:
    pass


@dataclass
class User:
    """Represents an User from the structure of the users.json file

    Attributes
    ----------
    sources : dict
        Store the sources which are readable for the user
    """

    _type: str
    groups: list
    id: str
    login: str
    name: str
    password: str
    source: str
    token: str
    allowSourceCreation: bool
    maxNumberCreatedSource: int

    # Specified as {"source_name": {"accessControl": "read", ...}, ...}
    sources: dict = field(init=False)

    def __post_init__(self):
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
