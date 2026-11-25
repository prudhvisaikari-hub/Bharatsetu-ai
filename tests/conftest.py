import os
os.environ["DEMO_MODE"] = "true"
os.environ["SEED_OWNER_PASSWORD"] = "test_owner_secure_pass_123"

import pytest
from backend import config
config.DEMO_MODE = True

from backend.db.database import engine, Base
from backend.store import seed_default_data
from backend.middleware import auth_limiter, global_limiter

@pytest.fixture(autouse=True)
def clean_db():
    auth_limiter.requests.clear()
    global_limiter.requests.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_default_data()
    yield
