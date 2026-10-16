
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware


DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {
        "true", "1", "yes", "on"
    }


def coerce(key, value):
    if key in {"port", "workers"}:
        return int(value)
    if key == "debug":
        return to_bool(value)
    return str(value)


def apply_layer(config, values):
    aliases = {
        "NUM_WORKERS": "workers",
        "APP_PORT": "port",
        "APP_WORKERS": "workers",
        "APP_DEBUG": "debug",
        "APP_LOG_LEVEL": "log_level",
        "APP_API_KEY": "api_key",
    }

    for key, value in values.items():
        if value is None:
            continue

        target = aliases.get(key, key)

        if target in DEFAULTS:
            config[target] = coerce(target, value)


def load_config():
    config = DEFAULTS.copy()

    environment = os.environ.get("APP_ENV", "development")
    yaml_file = BASE_DIR / f"config.{environment}.yaml"

    # Layer 1: YAML configuration
    if yaml_file.exists():
        with yaml_file.open("r", encoding="utf-8") as file:
            apply_layer(config, yaml.safe_load(file) or {})

    # Layer 2: .env file
    env_file = dotenv_values(BASE_DIR / ".env")
    apply_layer(config, env_file)

    # Layer 3: Operating-system environment variables
    apply_layer(config, os.environ)

    return config


@app.get("/effective-config")
def effective_config(set_values: list[str] | None = Query(
    default=None, alias="set"
)):
    config = load_config()

    # Layer 4: URL query overrides
    for item in set_values or []:
        if "=" not in item:
            continue

        key, value = item.split("=", 1)
        key = key.strip()

        if key in DEFAULTS:
            try:
                config[key] = coerce(key, value)
            except (ValueError, TypeError):
                continue

    # Never reveal the actual API key
    config["api_key"] = "****"

    return config
