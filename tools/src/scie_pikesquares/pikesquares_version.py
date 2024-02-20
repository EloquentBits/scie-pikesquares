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
    find_links: str | None

    def pikesquares_find_links_option(self, pikesquares_version_selected: Version) -> str:
        # We only want to add the find-links repo for PANTS_SHA invocations so that plugins can
        # resolve Pants the only place it can be found in that case - our ~private
        # binaries.pantsbuild.org S3 find-links bucket.
        operator = "-" if pikesquares_version_selected == self.stable_version else "+"
        option_name = (
            "repos"
            if self.stable_version in SpecifierSet("<2.14.0", prereleases=True)
            else "find-links"
        )
        value = f"'{self.find_links}'" if self.find_links else ""

        # we usually pass a no-op, e.g. --python-repos-find-links=-[], because this is only used for
        # PIKESQUARES_SHA support that is now deprecated and will be removed
        return f"--python-repos-{option_name}={operator}[{value}]"


def determine_find_links(
    ptex: Ptex,
    pikesquares_version: str,
    sha: str,
    find_links_dir: Path,
    include_nonrelease_pikesquares_distributions_in_findlinks: bool,
) -> ResolveInfo:
    abbreviated_sha = sha[:8]
    sha_version = Version(f"{pikesquares_version}+git{abbreviated_sha}")

    list_bucket_results = ElementTree.fromstring(
        ptex.fetch_text(f"https://binaries.pantsbuild.org?prefix=wheels/3rdparty/{sha}")
    )

    find_links_file = find_links_dir / pikesquares_version / abbreviated_sha / "index.html"
    find_links_file.parent.mkdir(parents=True, exist_ok=True)
    find_links_file.unlink(missing_ok=True)
    with find_links_file.open("wb") as fp:
        # N.B.: S3 bucket listings use a default namespace. Although the URI is apparently stable,
        # we decouple from it with the wildcard.
        for key in list_bucket_results.findall("./{*}Contents/{*}Key"):
            bucket_path = str(key.text)
            fp.write(
                f'<a href="https://binaries.pantsbuild.org/{urllib.parse.quote(bucket_path)}">'
                f"{os.path.basename(bucket_path)}"
                f"</a>{os.linesep}".encode()
            )
        fp.flush()
        if include_nonrelease_pikesquares_distributions_in_findlinks:
            pantsbuild_pants_find_links = (
                "https://binaries.pantsbuild.org/wheels/pantsbuild.pants/"
                f"{sha}/{urllib.parse.quote(str(sha_version))}/index.html"
            )
            ptex.fetch_to_fp(pantsbuild_pants_find_links, fp)
        fp.flush()

        ptex.fetch_to_fp("https://wheels.pantsbuild.org/simple/", fp)

    return ResolveInfo(
        stable_version=Version(pikesquares_version),
        sha_version=sha_version,
        find_links=f"file://{find_links_file}",
    )


def determine_tag_version(
    ptex: Ptex, pikesquares_version: str, find_links_dir: Path, github_api_bearer_token: str | None = None
) -> ResolveInfo:
    #stable_version = Version(pikesquares_version)
    #if stable_version >= PANTS_PEX_GITHUB_RELEASE_VERSION:
    #    return ResolveInfo(stable_version, sha_version=None, find_links=None)

    #tag = f"release_{pikesquares_version}"

    # N.B.: The tag database was created with the following in a Pants clone:
    # git tag --list release_* | \
    #   xargs -I@ bash -c 'jq --arg T @ --arg C $(git rev-parse @^{commit}) -n "{(\$T): \$C}"' | \
    #   jq -s 'add' > pants_release_tags.json
    #tags = json.loads(importlib.resources.read_text("scie_pikesquares", "pikesquares_release_tags.json"))
    #commit_sha = tags.get(tag, "")

    #if not commit_sha:
    #    mapping_file_url = f"https://binaries.pantsbuild.org/tags/pantsbuild.pants/{tag}"
    #    log.debug(
    #        f"Failed to look up the commit for Pants {tag} in the local database, trying a lookup "
    #        f"at {mapping_file_url} next."
    #    )
    #    try:
    #        commit_sha = ptex.fetch_text(mapping_file_url).strip()
    #    except CalledProcessError as e:
    #        log.debug(
    #            f"Failed to look up the commit for Pants {tag} at binaries.pantsbuild.org, trying "
    #            f"GitHub API requests next: {e}"
    #        )

    # The GitHub API requests are rate limited to 60 per hour un-authenticated; so we guard
    # these with the database of old releases and then the binaries.pantsbuild.org lookups above.
    #if not commit_sha:
    #    github_api_url = (
    #        f"https://api.github.com/repos/pantsbuild/pants/git/refs/tags/{urllib.parse.quote(tag)}"
    #    )
    #    headers = (
    #        {"Authorization": f"Bearer {github_api_bearer_token}"}
    #        if github_api_bearer_token
    #        else {}
    #    )
    #    github_api_tag_url = ptex.fetch_json(github_api_url, **headers)["object"]["url"]
    #    commit_sha = ptex.fetch_json(github_api_tag_url, **headers)["object"]["sha"]

    commit_sha=""

    return determine_find_links(
        ptex,
        pikesquares_version,
        commit_sha,
        find_links_dir,
        include_nonrelease_pikesquares_distributions_in_findlinks=False,
    )


def determine_sha_version(ptex: Ptex, sha: str, find_links_dir: Path) -> ResolveInfo:
    version_file_url = (
        f"https://raw.githubusercontent.com/pantsbuild/pants/{sha}/src/python/pants/VERSION"
    )
    pikesquares_version = ptex.fetch_text(version_file_url).strip()
    return determine_find_links(
        ptex,
        pikesquares_version,
        sha,
        find_links_dir,
        include_nonrelease_pikesquares_distributions_in_findlinks=True,
    )


def determine_latest_stable_version(
    ptex: Ptex, pikesquares_config: Path, find_links_dir: Path, github_api_bearer_token: str | None = None
) -> tuple[Callable[[], None], ResolveInfo]:
    info(f"Fetching latest stable PikeSquares version since none is configured")

    try:
        latest_tag = ptex.fetch_json(
            "https://github.com/pantsbuild/pants/releases/latest", Accept="application/json"
        )["tag_name"]
    except Exception as e:
        fatal(
            "Couldn't get the latest release by fetching https://github.com/pantsbuild/pants/releases/latest.\n\n"
            + "If this is unexpected (e.g. GitHub isn't down), please reach out on Slack: https://www.pantsbuild.org/docs/getting-help#slack\n\n"
            + f"Exception:\n\n{e}"
        )

    prefix, _, pikesquares_version = latest_tag.partition("_")
    if prefix != "release" or not pikesquares_version:
        fatal(
            f'Expected the GitHub Release tagged "latest" to have the "release_" prefix. Got "{latest_tag}"\n\n'
            + "Please reach out on Slack: https://www.pantsbuild.org/docs/getting-help#slack or file"
            + " an issue on GitHub: https://github.com/pantsbuild/pants/issues/new/choose."
        )

    def configure_version():
        backup = None
        if pikesquares_config.exists():
            info(f'Setting [GLOBAL] pikesquares_version = "{pikesquares_version}" in {pikesquares_config}')
            config = tomlkit.loads(pikesquares_config.read_text())
            backup = f"{pikesquares_config}.bak"
        else:
            info(f"Creating {pikesquares_config} and configuring it to use PikeSquares {pikesquares_version}")
            config = tomlkit.document()
        global_section = config.setdefault("GLOBAL", {})
        global_section["pikesquares_version"] = pikesquares_version
        if backup:
            warn(f"Backing up {pikesquares_config} to {backup}")
            pikesquares_config.replace(backup)
        pikesquares_config.write_text(tomlkit.dumps(config))

    return configure_version, determine_tag_version(
        ptex, pikesquares_version, find_links_dir, github_api_bearer_token
    )
