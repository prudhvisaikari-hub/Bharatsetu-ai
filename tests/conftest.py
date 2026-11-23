import pytest
import os
from backend.db.database import engine, Base
from backend.store import seed_default_data

@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_default_data()
    yield
