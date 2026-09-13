import pytest

from app.core.config import Settings


@pytest.mark.unit
def test_enable_test_endpoints_rejected_in_production() -> None:
    with pytest.raises(RuntimeError):
        Settings(environment="production", enable_test_endpoints=True)


@pytest.mark.unit
def test_enable_test_endpoints_allowed_outside_production() -> None:
    settings = Settings(environment="test", enable_test_endpoints=True)
    assert settings.enable_test_endpoints is True
