"""
script to update nbviewer

run via watch-dependencies.yaml workflow,
but can be run locally.

"""

import os
import shlex
from pathlib import Path
from subprocess import check_output

import requests
import yaml

nbviewer_deploy = Path(__file__).absolute().parents[1]
cd_yaml = nbviewer_deploy / ".github/workflows/cd.yml"
nbviewer_config_yaml = nbviewer_deploy / "config/nbviewer.yaml"


def _maybe_output(key, value):
    """Make outputs available to github actions (if running in github actions)"""
    github_output = os.environ.get("GITHUB_OUTPUT")
    line = f"{key}={shlex.quote(value)}"
    if github_output:
        with Path(github_output).open("a") as f:
            f.write(f"{line}\n")
    else:
        print(line)


def get_current_chart():
    """Get the current version of the chart in cd.yaml"""
    with cd_yaml.open() as f:
        cd = yaml.safe_load(f)
    chart_rev = cd["env"]["NBVIEWER_VERSION"]
    return chart_rev


def get_latest_chart():
    """Get the latest version of the chart repo"""
    out = check_output(
        ["git", "ls-remote", "https://github.com/jupyter/nbviewer", "HEAD"], text=True
    ).strip()
    return out.split()[0]


def get_current_image():
    """Get the current version of the nbviewer image in config"""
    with nbviewer_config_yaml.open() as f:
        config = yaml.safe_load(f)
    current_image = config["image"]
    return current_image


def get_latest_image():
    """Get the latest version of the nbviewer image from docker hub"""
    r = requests.get("https://hub.docker.com/v2/repositories/jupyter/nbviewer/tags")
    r.raise_for_status()
    tags = r.json()
    tag = tags["results"][0]["name"]
    return f"jupyter/nbviewer:{tag}"


def update_chart():
    """Update the version of the nbviewer chart to be deployed"""
    current_chart = get_current_chart()
    latest_chart = get_latest_chart()
    _maybe_output("chart_before", current_chart)
    _maybe_output("chart_after", latest_chart)
    _maybe_output("chart_short", latest_chart[:7])
    if latest_chart != current_chart:
        print(f"Updating {current_chart} -> {latest_chart} in {cd_yaml}")
        with cd_yaml.open() as f:
            current_yaml = f.read()
        modified_yaml = current_yaml.replace(current_chart, latest_chart, 1)
        with cd_yaml.open("w") as f:
            f.write(modified_yaml)


def update_image():
    """Update the version of the nbviewer image to be deployed"""
    current_image = get_current_image()
    latest_image = get_latest_image()
    _maybe_output("image_before", current_image)
    _maybe_output("image_after", latest_image)
    _maybe_output("image_tag", latest_image.partition(":")[2])

    if latest_image != current_image:
        print(f"Updating {current_image} -> {latest_image} in {nbviewer_config_yaml}")
        with nbviewer_config_yaml.open() as f:
            current_yaml = f.read()
        modified_yaml = current_yaml.replace(current_image, latest_image, 1)
        with nbviewer_config_yaml.open("w") as f:
            f.write(modified_yaml)


def main():
    update_chart()
    update_image()


if __name__ == "__main__":
    main()
