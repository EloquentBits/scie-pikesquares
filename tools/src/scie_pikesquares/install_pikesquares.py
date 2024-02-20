from __future__ import annotations

import json
import logging
import os
import stat
import subprocess
import sys
import tempfile
from argparse import ArgumentParser
from glob import glob
from pathlib import Path
from typing import Iterable, NoReturn

from packaging.version import Version

from scie_pikesquares.log import debug, fatal, info, init_logging
from scie_pikesquares.ptex import Ptex

log = logging.getLogger(__name__)


def venv_pip_install(venv_dir: Path, *args: str, find_links: str | None) -> None:
    subprocess.run(
        args=[
            str(venv_dir / "bin" / "python"),
            "-sE",
            "-m",
            "pip",
            # This internal 1-use pip need not nag the user about its up-to-date-ness.
            "--disable-pip-version-check",
            "--no-python-version-warning",
            "--log",
            str(venv_dir / "pikesquares-install.log"),
            "install",
            "--quiet",
            *(("--find-links", find_links) if find_links else ()),
            *args,
        ],
        check=True,
    )

def install_pikesquares_from_pex(
    venv_dir: Path,
    prompt: str,
    version: Version,
    ptex: Ptex,
    extra_requirements: Iterable[str],
    find_links: str | None,
    bootstrap_urls_path: str | None,
) -> None:
    """Installs PikeSquares into the venv using the platform-specific pre-built PEX."""
    uname = os.uname()
    #pex_name = f"pikesquares.{version}-cp39-{uname.sysname.lower()}_{uname.machine.lower()}.pex"
    pex_name = f"pikesquares-{uname.sysname.lower()}-{uname.machine.lower()}.pex"

    # https://github.com/EloquentBits/pikesquares/releases/download/0.1.2/pikesquares-linux-x86_64.pex
    # https://github.com/EloquentBits/pikesquares/releases/download/0.1.2/pikesquares-macos-arm64.pex
    # https://github.com/EloquentBits/pikesquares/releases/download/0.1.2/pikesquares-macos-x86_64.pex

    print(f"{pex_name=}")
    pex_url = f"https://github.com/EloquentBits/pikesquares/releases/download/{version}/{pex_name}"

    if bootstrap_urls_path:
        bootstrap_urls = json.loads(Path(bootstrap_urls_path).read_text())
        urls_info = bootstrap_urls["ptex"]
        pex_url = urls_info.get(pex_name)
        if pex_url is None:
            raise ValueError(
                f"Couldn't find '{pex_name}' in PIKESQUARES_BOOTSTRAP_URLS file: '{bootstrap_urls_path}' "
                "under the 'ptex' key."
            )
        if not isinstance(pex_url, str):
            raise TypeError(
                f"The value for the key '{pex_name}' in PIKESQUARES_BOOTSTRAP_URLS file: '{bootstrap_urls_path}' "
                f"under the 'ptex' key was expected to be a string. Got a {type(pex_url).__name__}"
            )

    with tempfile.NamedTemporaryFile(suffix=".pex") as pikesquares_pex:
        try:
            ptex.fetch_to_fp(pex_url, pikesquares_pex.file)
        except subprocess.CalledProcessError as e:
            #  if there's only one dot in version, specifically suggest adding the `.patch`)
            suggestion = (
                "PikeSquares version format not recognized. Please add `.<patch_version>` to the end of the version. For example: `2.18` -> `2.18.0`.\n\n"
                if version.base_version.count(".") < 2
                else ""
            )
            fatal(
                f"Wasn't able to fetch the PikeSquares PEX at {pex_url}.\n\n{suggestion}"
                "Check to see if the URL is reachable (i.e. GitHub isn't down) and if"
                f" {pex_name} asset exists within the release."
                f"Exception:\n\n{e}"
            )
        subprocess.run(
            args=[
                sys.executable,
                pikesquares_pex.name,
                "venv",
                "--prompt",
                prompt,
                "--compile",
                "--pip",
                "--collisions-ok",
                "--no-emit-warnings",  # Silence `PEXWarning: You asked for --pip ...`
                "--disable-cache",
                str(venv_dir),
            ],
            env={"PEX_TOOLS": "1"},
            check=True,
        )

    if extra_requirements:
        venv_pip_install(
            venv_dir, "--progress-bar", "off", *extra_requirements, find_links=find_links
        )


def chmod_plus_x(path: str) -> None:
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> NoReturn:
    parser = ArgumentParser()
    get_ptex = Ptex.add_options(parser)
    parser.add_argument(
        "--pikesquares-version", type=Version, required=True, help="The PikeSquares version to install"
    )
    parser.add_argument(
        "--find-links",
        type=str,
        help="The find links repo pointing to PikeSquares pre-built wheels for the given PikeSquares version",
    )
    parser.add_argument(
        "--pikesquares-bootstrap-urls",
        type=str,
        help="The path to the JSON file containing alternate URLs for downloaded artifacts.",
    )
    parser.add_argument("--debug", type=bool, help="Install with debug capabilities.")
    parser.add_argument("--debugpy-requirement", help="The debugpy requirement to install")
    parser.add_argument("base_dir", nargs=1, help="The base directory to create PikeSquares venvs in.")
    options = parser.parse_args()

    ptex = get_ptex(options)

    base_dir = Path(options.base_dir[0])
    init_logging(base_dir=base_dir, log_name="install")

    env_file = os.environ.get("SCIE_BINDING_ENV")
    if not env_file:
        fatal("Expected SCIE_BINDING_ENV to be set in the environment")

    venvs_dir = base_dir / "venvs"

    version = options.pikesquares_version
    python_version = ".".join(map(str, sys.version_info[:3]))
    info(f"Bootstrapping PikeSquares {version}")
    debug(f"PikeSquares itself is using: {sys.implementation.name} {python_version}")

    pikesquares_requirements = [f"pantsbuild.pants=={version}"]
    extra_requirements = []
    if options.debug:
        debugpy_requirement = options.debugpy_requirement or "debugpy==1.6.0"
        extra_requirements.append(debugpy_requirement)
        venv_dir = venvs_dir / f"{version}-{debugpy_requirement}"
        prompt = f"PikeSquares {version} [{debugpy_requirement}]"
    else:
        venv_dir = venvs_dir / str(version)
        prompt = f"PikeSquares {version}"

    info(
        f"Installing {' '.join(pikesquares_requirements + extra_requirements)} into a virtual environment at {venv_dir}"
    )
    install_pikesquares_from_pex(
        venv_dir=venv_dir,
        prompt=prompt,
        version=version,
        ptex=ptex,
        extra_requirements=extra_requirements,
        find_links=options.find_links,
        bootstrap_urls_path=options.pikesquares_bootstrap_urls,
    )
    info(f"New virtual environment successfully created at {venv_dir}.")

    pikesquares_server_exe = str(venv_dir / "bin" / "pikesquares")
    # Added in https://github.com/pantsbuild/pants/commit/558d843549204bbe49c351d00cdf23402da262c1
    native_client_binaries = glob(
        str(venv_dir / "lib/python*/site-packages/pants/bin/native_client")
    )
    pikesquares_client_exe = (
        native_client_binaries[0] if len(native_client_binaries) == 1 else pikesquares_server_exe
    )
    chmod_plus_x(pikesquares_client_exe)

    with open(env_file, "a") as fp:
        print(f"VIRTUAL_ENV={venv_dir}", file=fp)
        print(f"PIKESQUARES_SERVER_EXE={pikesquares_server_exe}", file=fp)
        print(f"PIKESQUARES_CLIENT_EXE={pikesquares_client_exe}", file=fp)

    sys.exit(0)


if __name__ == "__main__":
    main()
