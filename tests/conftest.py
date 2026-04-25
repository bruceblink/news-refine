import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeMappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def one_or_none(self):
        if not self._rows:
            return None
        return self._rows[0]


class FakeResult:
    def __init__(self, *, rows=None, scalar=None, all_rows=None):
        self._rows = rows or []
        self._scalar = scalar
        self._all_rows = all_rows or []

    def mappings(self):
        return FakeMappings(self._rows)

    def scalar_one(self):
        return self._scalar

    def all(self):
        return self._all_rows


class FakeBegin:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self, results=None):
        self._results = list(results or [])
        self.execute_calls = []

    async def execute(self, stmt):
        self.execute_calls.append(stmt)
        if self._results:
            return self._results.pop(0)
        return FakeResult()

    def begin(self):
        return FakeBegin()


class FakeSessionFactory:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def fake_result_cls():
    return FakeResult


@pytest.fixture
def fake_session_cls():
    return FakeSession


@pytest.fixture
def fake_session_factory_cls():
    return FakeSessionFactory
