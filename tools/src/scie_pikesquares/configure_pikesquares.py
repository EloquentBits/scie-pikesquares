from __future__ import annotations

import os
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import NoReturn

from tinydb import TinyDB, Query
from platformdirs import (
    user_data_dir, 
    site_runtime_dir,
    user_config_dir,
    user_log_dir,
)

from scie_pikesquares.log import fatal, info, init_logging, warn
from scie_pikesquares.pikesquares_version import (
    determine_latest_stable_version,
    determine_tag_version,
)
from scie_pikesquares.ptex import Ptex


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
    APP_NAME = "pikesquares"
    DATA_DIR = Path(user_data_dir(APP_NAME, ensure_exists=True))
    LOG_DIR = Path(user_log_dir(APP_NAME, ensure_exists=True))
    RUN_DIR = Path(site_runtime_dir(APP_NAME, ensure_exists=True))
    CONFIG_DIR = Path(user_config_dir(APP_NAME, ensure_exists=True))
    PLUGINS_DIR = DATA_DIR / 'plugins'
    PLUGINS_DIR.mkdir(mode=0o777, parents=True, exist_ok=True)
    PKI_DIR = DATA_DIR / 'pki'

    with open(env_file, "a") as fp:
        #print(f"PIKESQUARES_BUILDROOT_OVERRIDE=/home/pk/eqb/pikesquares", file=fp)
        print(f"PIKESQUARES_VERSION={version}", file=fp)
        print(f"PYTHON={python}", file=fp)

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
                "EASYRSA_DIR": os.environ.get("PIKESQUARES_EASY_RSA_DIR"),
                "PKI_DIR": str(PKI_DIR),
                "version": str(version),
            }, 
            Query().version == str(version),
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
