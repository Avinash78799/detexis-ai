import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('removal_benchmark', Path(__file__).parents[1] / 'tools/check_restored_removal.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)

DATABASE = 'postgresql+psycopg2://detexis:synthetic@db/shield_restore_012345abcdef_removal'
REDIS = 'redis://shield-removal-redis-012345abcdef:6379/0'


def test_only_disposable_fixture_targets_are_accepted():
    benchmark.validate_targets(DATABASE, REDIS)


@pytest.mark.parametrize('database,redis', [
    (DATABASE.replace('shield_restore_012345abcdef_removal', 'detexis'), REDIS),
    (DATABASE.replace('@db/', '@localhost/'), REDIS),
    (DATABASE + '?options=-csearch_path=other', REDIS),
    (DATABASE, 'redis://redis:6379/0'),
    (DATABASE, REDIS + '?other=1'),
    (DATABASE, REDIS.replace('/0','/1')),
])
def test_live_databases_shared_redis_and_target_overrides_are_refused(database, redis):
    with pytest.raises(ValueError):
        benchmark.validate_targets(database, redis)
