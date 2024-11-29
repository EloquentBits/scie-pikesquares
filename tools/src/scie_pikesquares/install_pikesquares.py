from __future__ import annotations

#import json
import logging
import os
import json
import pwd
#import stat
import subprocess
import sys
import tempfile
from argparse import ArgumentParser
#from glob import glob
from pathlib import Path
from typing import NoReturn

import questionary
from tinydb import TinyDB, Query
from packaging.version import Version
import platformdirs

from scie_pikesquares.log import debug, fatal, info, init_logging, warn
from scie_pikesquares.ptex import Ptex

log = logging.getLogger(__name__)

custom_style_dope = questionary.Style(
    [
        ("separator", "fg:#6C6C6C"),
        ("qmark", "fg:#FF9D00 bold"),
        ("question", ""),
        ("selected", "fg:#5F819D"),
        ("pointer", "fg:#FF9D00 bold"),
        ("answer", "fg:#5F819D bold"),
    ]
)


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

def get_uv_bin(platform):
    # uv-macos-x86_64/uv-x86_64-apple-darwin/
    # uv-linux-x86_64/uv-x86_64-unknown-linux-gnu
    # uv-macos-aarch64/uv-aarch64-apple-darwin/

    with open(os.environ.get("SCIE_LIFT_FILE"), 'r') as lift_file:
        
        lift_json  =json.loads(lift_file.read())
        lift_files = lift_json['scie']['lift']['files']
        file_name = f"uv-{platform}"
        uv_file = next(filter(lambda x: x.get("name") == file_name, lift_files))
        uv_dir = uv_file.get('key')
        uv_bin = Path(uv_dir) / "uv"
        print(f"{uv_bin=}")
        return uv_bin


def install_pikesquares_localdev(
    venv_dir: Path,
    localdev_dir: Path | None,
) -> None:

    #uv_bin = Path(os.environ.get("PIKESQUARES_UV_BIN"))
    #platform = "linux-x86_64"
    platform = f"{os.uname().sysname.lower()}-{os.uname().machine}"
    uv_bin = Path(os.environ.get("PIKESQUARES_UV_ROOT")) / get_uv_bin(platform)
    if not uv_bin.exists():
        raise Exception(f"unable to locate uv @ {uv_bin}")

    py_bin = Path(os.environ.get("PIKESQUARES_PYTHON_BIN"))
    if not py_bin.exists():
        print(f"unable to locate python @ {py_bin}")
        return

    try:
        compl = subprocess.run(
            args=[
                str(uv_bin),
                'sync',
                "--python",
                str(py_bin),
                "--verbose",
            ],
            env={
                "UV_PROJECT_ENVIRONMENT": str(venv_dir),
            },
            cwd=localdev_dir if localdev_dir else None,
            capture_output=True,
            check=True,
            #user="",
        )
    except subprocess.CalledProcessError as cperr:
        print(f"uv failed to sync dependencies: {cperr.stderr.decode()}")
        return

    if compl.returncode != 0:
        print("unable to install dependencies")

    print(compl.stderr.decode())
    print(compl.stdout.decode())


    cmd = f"""\
            UV_PROJECT_ENVIRONMENT={str(venv_dir)} {str(uv_bin)} sync --python {str(py_bin)} --verbose
            """
    print(cmd)

    #uv_venv(venv_dir, uv_bin, py_bin, localdev_dir)
    #uv_sync(venv_dir, uv_bin, py_bin, localdev_dir)
    #if localdev_dir:
    #    uv_add_pikesquares_editable(venv_dir, uv_bin, py_bin, localdev_dir)

###############################################################################
########################## legacy pip-based workflow

def install_pikesquares_localdev_pip(
    venv_dir: Path,
    log_dir: Path,
    localdev_dir: str,
) -> None:
    print(f"{os.environ.get('PIKESQUARES_UV_DIR')=}")
    print(f"{os.environ.get('PIKESQUARES_PYTHON_BIN')=}")

    subprocess.run(
        args=[
            sys.executable,
            "-m",
            "venv",
            #"--clear",
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
            str(log_dir / "pikesquares-install.log"),
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
            str(log_dir / "pikesquares-install.log"),
            "install",
            #"--quiet",
            "--editable",
            localdev_dir,
        ],
        check=True,
    )

    # pywsgi_wheel = "pikesquares_pyuwsgi-2.0.24.post0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
    # pyuwsgi = f"https://pypi.vc.eloquentbits.com/packages/{pywsgi_wheel}"

    # pyuwsgi-2.0.28.post1-cp312-cp312-macosx_13_0_arm64.whl (575.7 KB) 
    # pyuwsgi-2.0.28.post1-cp312-cp312-macosx_13_0_x86_64.whl (2.7 MB)  
    # pyuwsgi-2.0.28.post1-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

    subprocess.run(
        args=[
            str(venv_dir / "bin" / "python"),
            "-sE",
            "-m",
            "pip",
            "--disable-pip-version-check",
            "--no-python-version-warning",
            "--log",
            str(log_dir / "pikesquares-install.log"),
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

    APP_NAME="pikesquares"
    venv_dir = venvs_dir / str(version)
    pikesquares_server_exe = str(venv_dir / "bin" / "pikesquares")
    current_user: str = pwd.getpwuid(os.getuid()).pw_name
    data_dir = platformdirs.user_data_path(APP_NAME, current_user)
    log_dir = platformdirs.user_log_path(APP_NAME, current_user)
    config_dir = platformdirs.user_config_path(APP_NAME, current_user)

    #if "dev" in str(version):
    #    localdev_dir = os.environ.get("PIKESQUARES_LOCALDEV_DIR")
    if options.localdev_dir and Path(options.localdev_dir).exists():
        install_deps = True
        #if venv_dir.exists() and questionary.confirm(
        #        """Local PikeSquares dev venv exists. Skip installing dependencies?""",
        #        default=True, auto_enter=True, style="bold italic fg:yellow",).ask():
        #    install_deps = False

        if install_deps:
            install_pikesquares_localdev(
                venv_dir=venv_dir,
                localdev_dir=Path(options.localdev_dir)
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


    with open(env_file, "a") as fp:
        print(f"VIRTUAL_ENV={venv_dir}", file=fp)
        print(f"PIKESQUARES_SERVER_EXE={pikesquares_server_exe}", file=fp)
        print(f"PIKESQUARES_DATA_DIR={data_dir}", file=fp)
        print(f"PIKESQUARES_LOG_DIR={log_dir}", file=fp)
        print(f"PIKESQUARES_CONFIG_DIR={config_dir}", file=fp)
        print(f"PIKESQUARES_VERSION={version}", file=fp)

    with TinyDB(data_dir / "device-db.json") as db:
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
