from sqlmodel import SQLModel, Session, create_engine

from piios_backend.core.config import settings
from piios_backend.models import entities  # noqa: F401
from piios.decision_contracts.infrastructure import sqlmodel_entities as decision_sqlmodel_entities  # noqa: F401
from piios.thesis_health.infrastructure import sqlmodel_entities as thesis_health_sqlmodel_entities  # noqa: F401


engine = create_engine(settings.db_url, echo=False)


def init_db() -> None:
    global engine
    try:
        SQLModel.metadata.create_all(engine)
    except Exception:
        engine = create_engine("sqlite:///./piios_db.sqlite", echo=False)
        SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
