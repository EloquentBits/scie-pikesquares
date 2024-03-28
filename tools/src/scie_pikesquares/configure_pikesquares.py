from __future__ import annotations

from typing import Optional

import typer
from typing_extensions import Annotated

import os
import sys
import shutil
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import NoReturn

import questionary

from tinydb import TinyDB, Query
from platformdirs import (
    user_data_dir, 
    site_runtime_dir,
    user_config_dir,
    user_log_dir,
)
from packaging.version import Version

from scie_pikesquares.log import fatal, info, init_logging, warn, debug
from scie_pikesquares.pikesquares_version import (
    ResolveInfo,
    determine_latest_stable_version,
    #determine_tag_version,
)
from scie_pikesquares.ptex import Ptex


def prompt(message: str, default: bool) -> bool:
    raw_answer = input(f"{message} ({'Y/n' if default else 'N/y'}): ")
    answer = raw_answer.strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def prompt_for_pants_version(pants_config: Path) -> bool:
    warn(
        f"The `pants.toml` at {pants_config} has no `pants_version` configured in the `GLOBAL` "
        f"section."
    )
    return prompt(f"Would you like set `pants_version` to the latest stable release?", default=True)


def prompt_for_localdev_dir() -> Path | None:
    #cwd = os.getcwd()
    #buildroot = Path(cwd)
    #if shutil.which("git"):
    #    result = subprocess.run(
    #        args=["git", "rev-parse", "--show-toplevel"],
    #        stdout=subprocess.PIPE,
    #        stderr=subprocess.DEVNULL,
    #    )
    #    if result.returncode == 0:
    #        buildroot = Path(os.fsdecode(result.stdout.strip()))

    if prompt(f"Would you like to configure as a localdev project?", default=True):
        raw_answer = input(f"Provide the path to local repo of PikeSquares: ")
        answer = raw_answer.strip().lower()
        if Path(answer).exists():
            return Path(answer)


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

app = typer.Typer(
    no_args_is_help=True, 
    rich_markup_mode="rich"
)
@app.callback(invoke_without_command=True)
def main_typer(
    ctx: typer.Context,
    pikesquares_version: Annotated[
        str, 
        typer.Option("--pikesquares-version", help="PikeSquare Version to run")
    ],

    ptex_path: Annotated[
        Path, 
        typer.Option(
            "--ptex-path", 
            "-p", 
            exists=True,
            file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
            help="path to ptex",
        )
    ],

    base_dir: Annotated[
        Optional[Path], 
        typer.Argument(
            "--base-dir", 
            "-p", 
            exists=True,
            file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
            help="path to ptex",
        )
    ],

    verbose: Annotated[
        bool,
        typer.Option(help="Enable verbose mode.")] = False,

    ):

    obj = ctx.ensure_object(dict)
    obj["verbose"] = verbose

    #info(f"lift.bindings:configure {pikesquares_version=} {base_dir=} {ptex_path=} ")

    init_logging(base_dir=base_dir, log_name="configure")

    env_file = os.environ.get("SCIE_BINDING_ENV")
    localdev_dir = None

    if not env_file:
        fatal("Expected SCIE_BINDING_ENV to be set in the environment")

    #debug(f"lift.bindings.configure: {pikesquares_version=}")

    if pikesquares_version and "dev" in pikesquares_version:
        debug(f"configuring PikeSquares v{pikesquares_version} for Local Development ")
        resolve_info = ResolveInfo(stable_version=Version(pikesquares_version), sha_version=None)

        #localdev_dir = prompt_for_localdev_dir()
        #if not localdev_dir:
        #    warn("could not read the PikeSquares local dev directory. exiting.")
        #    sys.exit(1)

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

                if prompt(f"Would you like to configure {buildroot} as a localdev project?", default=True):
                    return buildroot

        #raw_answer = input(f"Provide the path to local repo of PikeSquares: ")
        #answer = raw_answer.strip().lower()
        #if Path(answer).exists():
        #    return Path(answer)

        localdev_dir = questionary.path(
                "Provide the path to local repo of PikeSquares: ", 
            default=os.getcwd(),
            only_directories=True,
            style=custom_style_dope,
        ).ask()
    #elif pikesquares_version:
        # fetch version 
    #    pass
    else:
        pt = Ptex(_exe=str(ptex_path))
        resolve_info = determine_latest_stable_version(ptex=pt)

    version = resolve_info.stable_version

    python = "cpython312"
    APP_NAME = "pikesquares"
    DATA_DIR = Path(user_data_dir(APP_NAME, ensure_exists=True))
    LOG_DIR = Path(user_log_dir(APP_NAME, ensure_exists=True))
    RUN_DIR = Path(site_runtime_dir(APP_NAME, ensure_exists=True))
    CONFIG_DIR = Path(user_config_dir(APP_NAME, ensure_exists=True))
    PLUGINS_DIR = DATA_DIR / 'plugins'
    PLUGINS_DIR.mkdir(mode=0o777, parents=True, exist_ok=True)
    PKI_DIR = DATA_DIR / 'pki'

    with open(env_file, "a") as fp:
        print(f"PIKESQUARES_VERSION={version}", file=fp)
        print(f"PYTHON={python}", file=fp)
        if localdev_dir:
            print(f"PIKESQUARES_LOCALDEV_DIR={str(localdev_dir)}", file=fp)
            info(f"wrote {localdev_dir=} to env_file....")

    with TinyDB(DATA_DIR / 'device-db.json') as db:
        conf_db = db.table('configs')
        conf_db.upsert(
            {
                "RUN_AS_UID": os.getuid(),
                "RUN_AS_GID": os.getgid(),
                "DATA_DIR": str(DATA_DIR),
                "RUN_DIR": str(RUN_DIR),
                "LOG_DIR": str(LOG_DIR),
                "CONFIG_DIR": str(CONFIG_DIR),
                "PLUGINS_DIR": str(PLUGINS_DIR),
                "EMPEROR_ZMQ_ADDRESS": "127.0.0.1:5250",
                "PKI_DIR": str(PKI_DIR),
                "SENTRY_DSN": os.environ.get("PIKESQUARES_SENTRY_DSN"),
                "version": str(version),
            }, 
            Query().version == str(version),
        )
    sys.exit(0)


def main() -> NoReturn:
    parser = ArgumentParser()
    get_ptex = Ptex.add_options(parser)
    parser.add_argument("--pikesquares-version", help="The PikeSquares version to install")
    parser.add_argument("base_dir", nargs=1, help="The base directory to create PikeSquares venvs in.")
    options = parser.parse_args()

    base_dir = Path(options.base_dir[0])
    init_logging(base_dir=base_dir, log_name="configure")

    env_file = os.environ.get("SCIE_BINDING_ENV")
    localdev_dir = None

    if not env_file:
        fatal("Expected SCIE_BINDING_ENV to be set in the environment")

    debug(f"lift.bindings.configure: {options.pikesquares_version=}")

    if options.pikesquares_version and "dev" in options.pikesquares_version:
        debug(f"configuring PikeSquares v{options.pikesquares_version} for Local Development ")
        resolve_info = ResolveInfo(stable_version=Version(options.pikesquares_version), sha_version=None)

        localdev_dir = prompt_for_localdev_dir()
        if not localdev_dir:
            warn("could not read the PikeSquares local dev directory. exiting.")
            sys.exit(1)
    else:
        resolve_info = determine_latest_stable_version(ptex=get_ptex(options))

    version = resolve_info.stable_version

    python = "cpython312"
    APP_NAME = "pikesquares"
    DATA_DIR = Path(user_data_dir(APP_NAME, ensure_exists=True))
    LOG_DIR = Path(user_log_dir(APP_NAME, ensure_exists=True))
    RUN_DIR = Path(site_runtime_dir(APP_NAME, ensure_exists=True))
    CONFIG_DIR = Path(user_config_dir(APP_NAME, ensure_exists=True))
    PLUGINS_DIR = DATA_DIR / 'plugins'
    PLUGINS_DIR.mkdir(mode=0o777, parents=True, exist_ok=True)
    PKI_DIR = DATA_DIR / 'pki'
    SENTRY_DSN="https://ac357cb22613711d55728418d91a53d1@sentry.eloquentbits.com/2"

    with open(env_file, "a") as fp:
        print(f"PIKESQUARES_VERSION={version}", file=fp)
        print(f"PYTHON={python}", file=fp)
        if localdev_dir:
            print(f"PIKESQUARES_LOCALDEV_DIR={str(localdev_dir)}", file=fp)

    with TinyDB(DATA_DIR / 'device-db.json') as db:
        conf_db = db.table('configs')
        conf_db.upsert(
            {
                "RUN_AS_UID": os.getuid(),
                "RUN_AS_GID": os.getgid(),
                "DATA_DIR": str(DATA_DIR),
                "RUN_DIR": str(RUN_DIR),
                "LOG_DIR": str(LOG_DIR),
                "CONFIG_DIR": str(CONFIG_DIR),
                "PLUGINS_DIR": str(PLUGINS_DIR),
                "EMPEROR_ZMQ_ADDRESS": "127.0.0.1:5250",
                "SENTRY_DSN": SENTRY_DSN,
                "PKI_DIR": str(PKI_DIR),
                "version": str(version),
            }, 
            Query().version == str(version),
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
    #typer.run(main)
    app()
