import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_the_two_model_names_exist():
    names = {m["model_name"] for m in load()["model_list"]}
    assert names == {"cheap-model", "strong-model"}


def test_strong_model_falls_back_to_cheap_model():
    fallbacks = load()["router_settings"]["fallbacks"]
    assert {"strong-model": ["cheap-model"]} in fallbacks


def test_master_key_comes_from_the_environment():
    key = load()["general_settings"]["master_key"]
    assert key == "os.environ/LITELLM_MASTER_KEY"


def test_no_database_url_in_the_gateway_config():
    # A database_url made the gateway answer "No connected db" on this PC.
    assert "database_url" not in load()["general_settings"]