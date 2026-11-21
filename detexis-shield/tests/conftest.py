import os
import sys
import tempfile
from pathlib import Path

import pytest

_database_dir = tempfile.TemporaryDirectory(prefix="shield-tests-", ignore_cleanup_errors=True)
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_database_dir.name) / "test.db").as_posix()
sys.path.insert(0, "backend")
sys.path.insert(0, "sensor-sdk")


@pytest.fixture(autouse=True)
def isolated_redis():
    import fakeredis
    from app.main import app
    from app.redis_store import get_redis
    fake = fakeredis.FakeRedis()
    app.dependency_overrides[get_redis] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_redis, None)
    fake.close()
