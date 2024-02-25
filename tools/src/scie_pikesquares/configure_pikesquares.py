from __future__ import annotations

import os
import shutil
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import NoReturn

from packaging.version import Version

from scie_pikesquares.log import fatal, info, init_logging, warn
from scie_pikesquares.pikesquares_version import (
    determine_latest_stable_version,
    determine_tag_version,
)
from scie_pikesquares.ptex import Ptex


def prompt(message: str, default: bool) -> bool:
    raw_answer = input(f"{message} ({'Y/n' if default else 'N/y'}): ")
    answer = raw_answer.strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def prompt_for_pikesquares_version(pikesquares_config: Path) -> bool:
    warn(
        f"The `pikesquares.toml` at {pikesquares_config} has no `pikesquares_version` configured in the `GLOBAL` "
        f"section."
    )
    return prompt(f"Would you like set `pikesquares_version` to the latest stable release?", default=True)


def prompt_for_pikesquares_config() -> Path | None:
    cwd = os.getcwd()
    buildroot = Path(cwd)
    if shutil.which("git"):
        result = subprocess.run(
            args=["git", "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            buildroot = Path(os.fsdecode(result.stdout.strip()))

    info(f"No PikeSquares configuration was found at or above {cwd}.")
    if prompt(f"Would you like to configure {buildroot} as a PikeSquares project?", default=True):
        return buildroot / "pikesquares.toml"
    return None


def main() -> NoReturn:
    parser = ArgumentParser()
    get_ptex = Ptex.add_options(parser)
    parser.add_argument("--pikesquares-version", help="The PikeSquares version to install")
    parser.add_argument("base_dir", nargs=1, help="The base directory to create PikeSquares venvs in.")
    options = parser.parse_args()

    base_dir = Path(options.base_dir[0])
    init_logging(base_dir=base_dir, log_name="configure")

    env_file = os.environ.get("SCIE_BINDING_ENV")

    if not env_file:
        fatal("Expected SCIE_BINDING_ENV to be set in the environment")

    ptex = get_ptex(options)

    if options.pikesquares_version:
        resolve_info = determine_tag_version(
            pikesquares_version=options.pikesquares_version,
        )
        version = resolve_info.stable_version
    else:
        resolve_info = determine_latest_stable_version(
            ptex=ptex,
        )
        version = resolve_info.stable_version

    python = "cpython312"

    print(f"writing to env file {env_file}")

    with open(env_file, "a") as fp:
        print(f"PIKESQUARES_VERSION={version}", file=fp)
        print(f"PYTHON={python}", file=fp)

    sys.exit(0)


if __name__ == "__main__":
    main()
