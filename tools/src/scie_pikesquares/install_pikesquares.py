from __future__ import annotations

#import json
import logging
import os
import pwd
#import stat
import subprocess
import sys
import tempfile
from argparse import ArgumentParser
#from glob import glob
from pathlib import Path
from typing import Iterable, NoReturn

from tinydb import TinyDB, Query
from packaging.version import Version
from platformdirs import user_data_dir

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

def install_pants_from_req(
    venv_dir: Path, prompt: str, pants_requirements: Iterable[str], find_links: str | None
) -> None:
    subprocess.run(
        args=[
            sys.executable,
            "-m",
            "venv",
            "--clear",
            "--prompt",
            prompt,
            str(venv_dir),
        ],
        check=True,
    )

    # Pin Pip to 22.3.1 (currently latest). The key semantic that should be preserved by the Pip
    # we use is that --find-links are used as a fallback only and PyPI is preferred. This saves us
    # money by avoiding fetching wheels from our S3 bucket at https://binaries.pantsbuild.org unless
    # absolutely needed.
    #
    # Also, we don't advance setuptools past 58 which drops support for the `setup` kwarg `use_2to3`
    # which Pants 1.x sdist dependencies (pystache) use.
    venv_pip_install(venv_dir, "-U", "pip==22.3.1", "setuptools<58", "wheel", find_links=find_links)
    venv_pip_install(venv_dir, "--progress-bar", "off", *pants_requirements, find_links=find_links)

def install_pikesquares_from_pex(
    venv_dir: Path,
    prompt: str,
    version: Version,
    ptex: Ptex,
) -> None:
    """Installs PikeSquares into the venv using the platform-specific pre-built PEX."""
    uname = os.uname()
    #pex_name = f"pikesquares.{version}-cp39-{uname.sysname.lower()}_{uname.machine.lower()}.pex"
    pex_name = f"pikesquares-{uname.sysname.lower()}-{uname.machine.lower()}.pex"

    # https://github.com/EloquentBits/pikesquares/releases/download/0.1.2/pikesquares-linux-x86_64.pex
    # https://github.com/EloquentBits/pikesquares/releases/download/0.1.2/pikesquares-macos-arm64.pex
    # https://github.com/EloquentBits/pikesquares/releases/download/0.1.2/pikesquares-macos-x86_64.pex

    pex_url = f"https://github.com/EloquentBits/pikesquares/releases/download/{version}/{pex_name}"

    with tempfile.NamedTemporaryFile(suffix=".pex") as pikesquares_pex:
        ptex.fetch_to_fp(pex_url, pikesquares_pex.file)
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

    pikesquares_requirements = [f"pikesquares=={version}"]
    venv_dir = venvs_dir / str(version)
    prompt = f"PikeSquares {version}"

    info(
        f"Installing {' '.join(pikesquares_requirements)} into a virtual environment at {venv_dir}"
    )
    install_pikesquares_from_pex(
        venv_dir=venv_dir,
        prompt=prompt,
        version=version,
        ptex=ptex,
    )
    info(f"New virtual environment successfully created at {venv_dir}.")

    pikesquares_server_exe = str(venv_dir / "bin" / "pikesquares")
    current_user: str = pwd.getpwuid(os.getuid()).pw_name
    pikesquares_data_dir = Path(user_data_dir("pikesquares", current_user))
    with open(env_file, "a") as fp:
        print(f"VIRTUAL_ENV={venv_dir}", file=fp)
        print(f"PIKESQUARES_SERVER_EXE={pikesquares_server_exe}", file=fp)
        print(f"PIKESQUARES_DATA_DIR={pikesquares_data_dir}", file=fp)

    with TinyDB(Path(pikesquares_data_dir) / "device-db.json") as db:
        conf_db = db.table('configs')
        conf_db.upsert(
            {
                'VIRTUAL_ENV': str(venv_dir),
            },
            Query().version == str(version),
        )
        print(f"wrote venv dir to config. {version=}")

    sys.exit(0)


if __name__ == "__main__":
    main()