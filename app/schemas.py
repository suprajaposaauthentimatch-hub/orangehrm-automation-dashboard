from pydantic import BaseModel, Field, SecretStr

class AutomationInput(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: SecretStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    employee_id: str = Field(min_length=1, max_length=30)
