import pytest
from pydantic import ValidationError

from app.schemas import AutomationInput

def test_valid_payload_keeps_password_secret():
    payload = AutomationInput(username="Admin", password="secret", first_name="Ada", last_name="Lovelace", employee_id="9001")
    assert payload.password.get_secret_value() == "secret"
    assert "secret" not in repr(payload)

def test_required_values_are_validated():
    with pytest.raises(ValidationError):
        AutomationInput(username="", password="", first_name="Ada", last_name="Lovelace", employee_id="9001")
