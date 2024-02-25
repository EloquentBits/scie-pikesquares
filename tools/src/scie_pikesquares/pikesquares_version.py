from __future__ import annotations

import importlib.resources
import json
import logging
import os
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from subprocess import CalledProcessError
from typing import Callable
from xml.etree import ElementTree

import tomlkit
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from scie_pikesquares.log import fatal, info, warn
from scie_pikesquares.ptex import Ptex

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class ResolveInfo:
    stable_version: Version
    sha_version: Version | None


def determine_tag_version(
    pikesquares_version: str, 
) -> ResolveInfo:
    tag = f"{pikesquares_version}"
    # N.B.: The tag database was created with the following in a Pants clone:
    # git tag --list release_* | \
    #   xargs -I@ bash -c 'jq --arg T @ --arg C $(git rev-parse @^{commit}) -n "{(\$T): \$C}"' | \
    #   jq -s 'add' > pants_release_tags.json
    tags = json.loads(importlib.resources.read_text("scie_pikesquares", "pikesquares_release_tags.json"))
    commit_sha = tags.get(tag, "")

    return ResolveInfo(
        stable_version=Version(pikesquares_version),
        sha_version=commit_sha,
    )

def determine_latest_stable_version(
    ptex: Ptex, 
) -> ResolveInfo:
    info(f"Fetching latest stable PikeSquares version since none is configured")

    try:
        latest_tag = ptex.fetch_json(
            "https://github.com/eloquentbits/pikesquares/releases/latest", Accept="application/json"
        )["tag_name"]
    except Exception as e:
        fatal(
            "Couldn't get the latest release by fetching https://github.com/eloquentbits/pikesquares/releases/latest.\n\n"
            + f"Exception:\n\n{e}"
        )

    prefix, _, pikesquares_version = latest_tag.partition("_")
    if prefix != "release" or not pikesquares_version:
        fatal(
            f'Expected the GitHub Release tagged "latest" to have the "release_" prefix. Got "{latest_tag}"\n\n'
        )

    return ResolveInfo(
        stable_version=Version(pikesquares_version),
        sha_version=None,
    )
