"""
Pytest fixtures. Uses a throwaway SQLite file DB (not Postgres) purely to
keep the test suite fast and dependency-free — application code itself
targets Postgres in production (see app/config.py DATABASE_URL).
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import RmftMaster

RMFT_SEED = [
    ("00380727", "Adist Ayudistira"),
    ("00382271", "Ahmad Rafiq"),
    ("00274689", "Dia Silopa"),
]


@pytest.fixture()
def db_session():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    for pn, name in RMFT_SEED:
        session.add(RmftMaster(pn=pn, rmft_name=name, active=True))
    session.commit()
    yield session
    session.close()
    os.unlink(path)
