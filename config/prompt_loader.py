import yaml

def load_prompt():

    with open(
        "config/prompts.yaml",
        "r",
        encoding="utf-8"
    ) as f:

        config = yaml.safe_load(f)

    return config["system_prompt"]