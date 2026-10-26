import pytest

from reliablebiz.config import PROJECT_ROOT
from reliablebiz.datastore import DataStore


@pytest.fixture(scope="session")
def store() -> DataStore:
    return DataStore.from_dir(PROJECT_ROOT / "data")
