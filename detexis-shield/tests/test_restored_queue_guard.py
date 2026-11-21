import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("restored_queue", Path("tools/check_restored_queue.py"))
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

DATABASE = "postgresql+psycopg2://detexis:synthetic@db/shield_restore_fixture_replay"
REDIS = "redis://shield-replay-redis-123abc:6379/0"


def test_replay_accepts_only_isolated_restore_and_dedicated_redis():
    tool.validate_targets(DATABASE, REDIS)
    for database in [DATABASE.replace("fixture_replay", "fixture"),
                     DATABASE.replace("shield_restore_fixture_replay", "detexis"),
                     DATABASE.replace("@db/", "@localhost/"), "sqlite:///test.db"]:
        with pytest.raises(ValueError):
            tool.validate_targets(database, REDIS)
    for redis in ["redis://redis:6379/0", REDIS.replace("/0", "/1"),
                  REDIS.replace(":6379", ":6380"), REDIS + "?bad=1",
                  REDIS.replace("redis://", "redis://password@")]:
        with pytest.raises(ValueError):
            tool.validate_targets(DATABASE, redis)
