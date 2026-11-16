"""Fixed ids for seeded content (uuid5), so seeding is repeatable and tests can refer to rows."""

import uuid

_NS = uuid.UUID("6f1c1c2e-6a59-4f8e-9f57-1e0b8f1a6c00")


def seed_id(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)
