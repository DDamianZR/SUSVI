from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mock_mode: bool = True
    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    watsonx_model_id: str = "ibm/granite-13b-instruct-v2"
    api_port: int = 8000

    class Config:
        env_file = ".env"

settings = Settings()
