from __future__ import annotations

import os
import pwd
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import NoReturn

from platformdirs import (
    user_data_dir, 
    user_runtime_dir,
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
    current_user: str = pwd.getpwuid(os.getuid()).pw_name
    APP_NAME = "pikesquares"
    DATA_DIR = Path(user_data_dir(APP_NAME, current_user))

    with open(env_file, "a") as fp:
        print(f"PIKESQUARES_VERSION={version}", file=fp)
        print(f"PYTHON={python}", file=fp)
        print(f"RUN_AS_UID={os.getuid()}", file=fp)
        print(f"RUN_AS_GID={os.getgid()}", file=fp)
        print(f"DATA_DIR={DATA_DIR}", file=fp)
        print(f"RUN_DIR={str(Path(user_runtime_dir(APP_NAME, current_user)).resolve())}", file=fp)
        print(f"LOG_DIR={str(Path(user_log_dir(APP_NAME, current_user)).resolve())}", file=fp)
        print(f"CONFIG_DIR={str(Path(user_config_dir(APP_NAME, current_user)).resolve())}", file=fp)
        print(f"PLUGINS_DIR={DATA_DIR / 'plugins'}", file=fp)
        print(f"EMPEROR_ZMQ_ADDRESS=127.0.0.1:5250", file=fp)
        print(f"PKI_DIR={DATA_DIR / 'pki'}", file=fp)

    sys.exit(0)


if __name__ == "__main__":
    main()
