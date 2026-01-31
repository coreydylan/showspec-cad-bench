from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    freecad_path: str = "/usr/bin/freecad"
    template_dir: str = "/app/templates"
    material_library: str = "/app/materials/material_library.json"
    labor_rates: str = "/app/materials/labor_rates.json"
    log_level: str = "INFO"

    # AWS (for S3 template storage in production)
    aws_region: str = "us-west-2"
    s3_template_bucket: str = ""

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
