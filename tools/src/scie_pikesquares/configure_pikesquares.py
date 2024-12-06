from __future__ import annotations

import os
import pwd
import sys
import subprocess
import shutil
#import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import NoReturn

import questionary

from tinydb import TinyDB, Query
import platformdirs 
from packaging.version import Version

from scie_pikesquares.log import fatal, info, init_logging, warn, debug
from scie_pikesquares.pikesquares_version import (
    ResolveInfo,
    determine_latest_stable_version,
    #determine_tag_version,
)
from scie_pikesquares.ptex import Ptex


class UWSGIBuildError(Exception):
    pass


def prompt(message: str, default: bool) -> bool:
    raw_answer = input(f"{message} ({'Y/n' if default else 'N/y'}): ")
    answer = raw_answer.strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")

"""

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

"""

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

def get_latest_config(db_path):
    if (db_path).exists():
        with TinyDB(db_path) as db:
            return db.table("configs").get(
                Query().version == max([c.get('version') for c in db.table("configs").all()])
            )[0]

def init_submodules():
    cmd = "git submodule update --init --recursive"
    try:
        compl = subprocess.run(
            cmd,
            env={},
            shell=True,
            cwd=Path.cwd(),
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as cperr:
        print(f"failed to init submodules: {cperr.stderr.decode()}")
        return

    if compl.returncode != 0:
        print("unable to init submodules")

    #Submodule 'uwsgi' (git@github.com:unbit/uwsgi.git) registered for path 'uwsgi'
    #Cloning into '/home/pk/dev/eqb/tmp/scie-pikesquares/uwsgi'...
    #Submodule path 'uwsgi': checked out '02a2fc47c7cd32a5c0d1e07808f36cbe1533ecbe'

    print(compl.stderr.decode())
    print(compl.stdout.decode())

def build_plugin(plugin:str, python_bin: Path, plugins_dir: Path):
    plugin_name = plugin
    if plugin == "python":
        py_version = "312"
        plugin_name = f"python{py_version}"
    
    try:
        compl = subprocess.run(
            f"{python_bin.resolve()} ./uwsgiconfig.py --plugin plugins/{plugin} pikesquares {plugin_name}",
            env=os.environ,
            shell=True,
            cwd=Path.cwd() / "uwsgi",
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as cperr:
        print(f"failed to build uWSGI plugin '{plugin}': {cperr.stderr.decode()}")
        return

    if compl.returncode != 0:
        print(f"unable to build uWSGI plugin '{plugin}'")

    print(compl.stderr.decode())
    print(compl.stdout.decode())

    dest = Path(f"uwsgi/{plugin_name}_plugin.so").resolve()
    src = (Path(plugins_dir) / f"{plugin_name}_plugin.so").resolve()
    try:
        src.symlink_to(dest)
    except FileExistsError:
        pass


def build_uwsgi(python_bin: Path):
    shutil.copy(Path("pikesquares.ini"), Path("uwsgi/buildconf/pikesquares.ini"))
    try:
        compl = subprocess.run(
            f"{python_bin.resolve()} ./uwsgiconfig.py --build pikesquares",
            env=os.environ,
            shell=True,
            cwd=Path.cwd() / "uwsgi",
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as cperr:
        print(f"failed to build uWSGI binary: {cperr.stderr.decode()}")
        return

    if compl.returncode != 0:
        print("unable to build uWSGI binary")

    print(compl.stderr.decode())
    print(compl.stdout.decode())



def main() -> NoReturn:
    parser = ArgumentParser()
    get_ptex = Ptex.add_options(parser)
    parser.add_argument("--pikesquares-version", help="The PikeSquares version to install")
    parser.add_argument("base_dir", nargs=1, help="The base directory to create PikeSquares venvs in.")
    options = parser.parse_args()

    base_dir = Path(options.base_dir[0])
    init_logging(base_dir=base_dir, log_name="configure")

    #argv0 = os.environ.get("SCIE_ARGV0")
    #print(f"scie-pikesquares: {argv0=}")

    for key, value in os.environ.items():
        if key.startswith(("PIKESQUARES", "SCIE", "PEX", "UV")):
            print(f' === {key}: {value}')
        #else:
        #    print(f'{key}: {value}')

    env_file = os.environ.get("SCIE_BINDING_ENV")
    localdev_dir = None

    if not env_file:
        fatal("Expected SCIE_BINDING_ENV to be set in the environment")

    debug(f"lift.bindings.configure: {options.pikesquares_version=}")
    print(f"lift.bindings.configure: {options.pikesquares_version=}")

    python = "cpython312"
    APP_NAME = "pikesquares"
    current_uid = os.getuid()
    current_gid = os.getgid()
    server_run_as_uid = current_uid
    server_run_as_gid = current_gid
    new_server_run_as_uid = None
    new_server_run_as_gid = None
    apps_run_as_uid = None
    apps_run_as_gid = None

    if 0 and current_uid != 0:
        db_path = platformdirs.user_data_path(APP_NAME) / 'device-db.json'
        try:
            latest_config = get_latest_config(db_path)
            configured_uid = latest_config.get("SERVER_RUN_AS_UID") 
            configured_gid = latest_config.get("SERVER_RUN_AS_GID") 

            configured_apps_uid = latest_config.get("RUN_AS_UID") 
            configured_apps_gid = latest_config.get("RUN_AS_GID") 

            if not all([
                configured_uid in [current_uid, 0],
                configured_gid in [current_gid, 0],
                ]):
                questionary.print(
                    f"""You have previously selected to run \n
                    the PikeSquares Server as user id `{configured_uid}` and group id `{configured_gid}`\n
                    Your current user id is `{current_uid}` and group id `{current_gid}`\n""",
                    style="bold italic fg:yellow"
                )
            elif configured_uid == 0 and configured_gid == 0:
                questionary.print(
                    f"""You have previously selected to run the PikeSquares Server as root user"\n
                    Your current user id is `{current_uid}` and group id `{current_gid}`\n
                    """,
                    style="bold italic fg:yellow"
                )
            if not questionary.confirm(
                f"""Exit now and launch the PikeSquares Server as your previously selected user `{configured_uid}`?\
                Choosing to continue will prompt you to select a new value for the unpriviledged user and group.""",
                #instruction="",
                ).ask():

                new_server_run_as_uid = questionary.text(
                    "Please provide a user name or uid to run the PikeSquares Server as:",
                    default=pwd.getpwuid(current_uid).pw_name,
                ).ask()
                new_server_run_as_gid = questionary.text(
                    "Please provide a group name or gid to run the PikeSquares Server as:",
                    default=pwd.getpwuid(current_gid).pw_name,
                ).ask()
                questionary.print(f"{new_server_run_as_gid=} {new_server_run_as_gid=}")

            elif configured_uid == current_uid and configured_gid == current_gid:
                pass

        except IndexError:
            pass

        if not any([new_server_run_as_uid, new_server_run_as_gid]):
            questionary.print(
                """Looks like you are running the PikeSquares Server as an unpriviledged user.\n
                While this is supported, there are a number of advantages to launching the PikeSquares Server as root\n
                such as being able to bind to non-priviledged ports, i.e. 80 and 443.\n
                Launching the PikeSquares Server as root, i.e. `sudo pikesquares up`, your apps can still run as an unpriviledged user of your choice.\n """, 
                style="bold italic fg:yellow"
            )
            if questionary.confirm(
                "Exit now so that you can launch as root? Choosing to continue will prompt you to select an unpriviledged user.",
                #instruction="",
                ).ask():
                questionary.print(
                    """Please launch the PikeSquares Server as root `sudo pikesquares up` """, 
                    style="bold italic fg:yellow",
                )
                sys.exit(0)
            else:
                new_server_run_as_uid = questionary.text(
                    "Please provide a user name or uid to run the PikeSquares Server as:",
                    default=pwd.getpwuid(current_uid).pw_name,
                ).ask()
                new_server_run_as_gid = questionary.text(
                    "Please provide a group name or gid to run the PikeSquares Server as:",
                    default=pwd.getpwuid(current_gid).pw_name,
                ).ask()
                questionary.print(f"{new_server_run_as_uid=} {new_server_run_as_gid=}")

    if current_uid == 0:
        DATA_DIR = platformdirs.user_data_path(APP_NAME, ensure_exists=True)
        LOG_DIR = platformdirs.user_log_path(APP_NAME, ensure_exists=True)
        RUN_DIR = platformdirs.site_runtime_path(APP_NAME, ensure_exists=True)
        CONFIG_DIR = platformdirs.user_config_path(APP_NAME, ensure_exists=True)

    else:
        DATA_DIR = platformdirs.user_data_path(APP_NAME, ensure_exists=True)
        LOG_DIR = platformdirs.user_log_path(APP_NAME, ensure_exists=True)
        RUN_DIR = platformdirs.user_runtime_path(APP_NAME, ensure_exists=True)
        CONFIG_DIR = platformdirs.user_config_path(APP_NAME, ensure_exists=True)

    PLUGINS_DIR = DATA_DIR / 'plugins'
    PLUGINS_DIR.mkdir(mode=0o777, parents=True, exist_ok=True) 

    if options.pikesquares_version and "dev" in options.pikesquares_version:
        debug(f"configuring PikeSquares v{options.pikesquares_version} for Local Development ")
        resolve_info = ResolveInfo(stable_version=Version(options.pikesquares_version), sha_version=None)

        localdev_dir_in_parent = None
        if (Path.cwd().parent / "pikesquares").exists():
            localdev_dir_in_parent = Path.cwd().parent / "pikesquares"

        localdev_dir = questionary.path(
            "Provide the path to local repo of PikeSquares: ", 
            default=str(localdev_dir_in_parent) or os.getcwd(),
            only_directories=True,
            style=custom_style_dope,
        ).ask()

        if not localdev_dir:
            warn("could not read the PikeSquares local dev directory. exiting.")
            sys.exit(1)

        uwsgi_dir = Path("uwsgi")
        if not uwsgi_dir.exists():
            init_submodules()
            print("unable to init git submodules")
            #python_bin = os.environ.get('PIKESQUARES_PYTHON_BIN')
            python_bin = Path("/usr/bin/python3")
            if not python_bin.exists():
                raise UWSGIBuildError(f"cannot locate python at {python_bin}")
            try:
                build_uwsgi(python_bin)
                build_plugin("corerouter", python_bin, PLUGINS_DIR)
                build_plugin("http", python_bin, PLUGINS_DIR)
                build_plugin("python", python_bin, PLUGINS_DIR)
                build_plugin("logfile", python_bin, PLUGINS_DIR)
            except Exception as exc:
                raise UWSGIBuildError(f"unable to build uWSGI {str(exc)}")
    else:
        resolve_info = determine_latest_stable_version(ptex=get_ptex(options))

    version = resolve_info.stable_version
    #process_compose_config = "/home/pk/dev/eqb/pikesquares/process-compose.yml"

    with open(env_file, "a") as fp:
        print(f"PIKESQUARES_VERSION={version}", file=fp)
        print(f"PYTHON={python}", file=fp)
        #print(f"PIKESQUARES_PROCESS_COMPOSE_CONFIG={process_compose_config}", file=fp)
        if localdev_dir:
            print(f"PIKESQUARES_LOCALDEV_DIR={str(localdev_dir)}", file=fp)

    with TinyDB(DATA_DIR / 'device-db.json') as db:
        conf_db = db.table('configs')
        conf_db.upsert(
            {
                "RUN_AS_UID": apps_run_as_uid or current_uid,
                "RUN_AS_GID": apps_run_as_gid or current_gid,
                "SERVER_RUN_AS_UID": new_server_run_as_uid or server_run_as_uid,
                "SERVER_RUN_AS_GID": new_server_run_as_gid or server_run_as_gid,
                "DATA_DIR": str(DATA_DIR),
                "RUN_DIR": str(RUN_DIR),
                "LOG_DIR": str(LOG_DIR),
                "CONFIG_DIR": str(CONFIG_DIR),
                "PLUGINS_DIR": str(PLUGINS_DIR),
                "EASYRSA_DIR": os.environ.get("PIKESQUARES_EASYRSA_DIR"),
                "EASYRSA_BIN": os.environ.get("PIKESQUARES_EASYRSA_BIN"),
                "SENTRY_DSN": os.environ.get("PIKESQUARES_SENTRY_DSN"),
                "PKI_DIR": str(DATA_DIR / 'pki'),
                "version": str(version),
            }, 
            Query().version == str(version),
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
