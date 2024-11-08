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
from typing import NoReturn

from tinydb import TinyDB, Query
from packaging.version import Version
from platformdirs import user_data_dir

from scie_pikesquares.log import debug, fatal, info, init_logging, warn
from scie_pikesquares.ptex import Ptex

log = logging.getLogger(__name__)


def install_pikesquares_from_pex(
    venv_dir: Path,
    prompt: str,
    version: Version,
    ptex: Ptex,
) -> None:
    """Installs PikeSquares into the venv using the platform-specific pre-built PEX."""
    uname = os.uname()
    OS = "macos" if uname.sysname.lower() == "darwin" else "linux"
    pex_name = f"pikesquares-{OS}-{uname.machine.lower()}.pex"
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

def install_pikesquares_localdev(
    venv_dir: Path,
    localdev_dir: str,
) -> None:

    subprocess.run(
        args=[
            sys.executable,
            "-m",
            "venv",
            "--clear",
            str(venv_dir),
        ],
        check=True,
    )
    #venv_pip_install(venv_dir, "-U", "pip==22.3.1", "setuptools<58", "wheel", find_links=find_links)
    #venv_pip_install(venv_dir, "--progress-bar", "off", *pants_requirements, find_links=find_links)

    subprocess.run(
        args=[
            str(venv_dir / "bin" / "python"),
            "-sE",
            "-m",
            "pip",
            "--disable-pip-version-check",
            "--no-python-version-warning",
            "--log",
            str(venv_dir / "pikesquares-install.log"),
            "install",
            #"--quiet",
            "--requirement",
            str(Path(localdev_dir) / "requirements.txt"),
        ],
        check=True,
    )

    subprocess.run(
        args=[
            str(venv_dir / "bin" / "python"),
            "-sE",
            "-m",
            "pip",
            "--disable-pip-version-check",
            "--no-python-version-warning",
            "--log",
            str(venv_dir / "pikesquares-install.log"),
            "install",
            #"--quiet",
            "--editable",
            localdev_dir,
        ],
        check=True,
    )

    # pywsgi_wheel = "pikesquares_pyuwsgi-2.0.24.post0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
    # pyuwsgi = f"https://pypi.vc.eloquentbits.com/packages/{pywsgi_wheel}"

    subprocess.run(
        args=[
            str(venv_dir / "bin" / "python"),
            "-sE",
            "-m",
            "pip",
            "--disable-pip-version-check",
            "--no-python-version-warning",
            "--log",
            str(venv_dir / "pikesquares-install.log"),
            "install",
            #"--quiet",
            "--trusted-host",
            "pypi.vc.eloquentbits.com",
            "-i",
            "https://pypi.vc.eloquentbits.com",
            "pyuwsgi==2.0.28.post1",
        ],
        check=True,
    )


def main() -> NoReturn:
    parser = ArgumentParser()
    get_ptex = Ptex.add_options(parser)
    parser.add_argument(
        "--pikesquares-version", type=Version, required=True, help="The PikeSquares version to install"
    )
    parser.add_argument("--debug", type=bool, help="Install with debug capabilities.")
    parser.add_argument("--localdev-dir", type=str, help="PikeSquares repo as editable install.")
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
    debug(f"lift.bindings.install: Bootstrapping PikeSquares {version}")
    #python_version = ".".join(map(str, sys.version_info[:3]))
    #debug(f"PikeSquares itself is using: {sys.implementation.name} {python_version}")

    venv_dir = venvs_dir / str(version)

    #if "dev" in str(version):
    #    localdev_dir = os.environ.get("PIKESQUARES_LOCALDEV_DIR")
    if options.localdev_dir and Path(options.localdev_dir).exists():
        install_pikesquares_localdev(
            venv_dir=venv_dir,
            localdev_dir=options.localdev_dir
        )
    else:
        install_pikesquares_from_pex(
            venv_dir=venv_dir,
            prompt=f"PikeSquares {version}",
            version=version,
            ptex=ptex,
        )
        info(
            f"Installing pikesquares=={version} into a virtual environment at {venv_dir}"
        )
    info(f"New virtual environment successfully created at {venv_dir}")

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

    sys.exit(0)


if __name__ == "__main__":
    main()
