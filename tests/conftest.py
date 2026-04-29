import pytest

@pytest.fixture
def sample_faction_id() -> str:
    return "ussf"

@pytest.fixture
def sample_turn() -> int:
    return 1
