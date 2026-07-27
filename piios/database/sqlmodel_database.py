from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine


metadata = SQLModel.metadata


@dataclass(frozen=True)
class DatabaseConfig:
    db_url: str
    echo: bool = False


def build_engine(config: DatabaseConfig):
    return create_engine(config.db_url, echo=config.echo)


def build_session_factory(engine):
    def _factory() -> Session:
        return Session(engine)

    return _factory


def get_session(session_factory) -> Iterator[Session]:
    with session_factory() as session:
        yield session
