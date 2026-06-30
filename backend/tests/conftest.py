import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

# Single in-memory SQLite shared across all sessions via StaticPool.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def db():
    """Fresh empty DB per test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):  # db first so tables exist before TestClient starts
    with TestClient(app) as c:
        yield c


@pytest.fixture
def enable_brightdata(monkeypatch):
    """Patch the module-level var so fetch_unit_prices thinks pricing is enabled."""
    import app.services.brightdata_client as mod
    monkeypatch.setattr(mod, "BRIGHTDATA_PRICING_URL", "http://fake-pricing.test")
    yield "http://fake-pricing.test"
