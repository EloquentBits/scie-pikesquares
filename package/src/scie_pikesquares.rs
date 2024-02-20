use std::io::Write;
use std::path::{Path, PathBuf};

use anyhow::Result;
use termcolor::WriteColor;

use crate::utils::build::{BuildContext, Science};
use crate::utils::exe::{binary_full_name, execute};
use crate::utils::fs::{ensure_directory, path_as_str};
use crate::{build_step, BINARY};

pub(crate) struct SciePikeSquaresBuild {
    pub(crate) exe: PathBuf,
    pub(crate) sha256: PathBuf,
}

pub(crate) fn build_scie_pikesquares_scie(
    build_context: &BuildContext,
    science: &Science,
    scie_pikesquares_exe: &Path,
    tools_pex_file: &Path,
) -> Result<SciePikeSquaresBuild> {
    build_step!("Building the `scie-pikesquares` scie");

    let scie_pikesquares_package_dir = build_context.cargo_output_root.join("scie-pikesquares");
    ensure_directory(&scie_pikesquares_package_dir, true)?;

    let scie_pikesquares_manifest = build_context
        .package_crate_root
        .join("scie-pikesquares.toml")
        .strip_prefix(&build_context.workspace_root)?
        .to_owned();

    // N.B.: We name the scie-pikesquares binary scie-pikesquares.bin since the scie itself is named scie-pikesquares
    // which would conflict when packaging.
    execute(
        science
            .command()
            .args([
                "lift",
                "--include-provenance",
                "--file",
                &format!(
                    "scie-pikesquares.bin={scie_pikesquares_exe}",
                    scie_pikesquares_exe = path_as_str(scie_pikesquares_exe)?
                ),
                "--file",
                &format!(
                    "tools.pex={tools_pex}",
                    tools_pex = path_as_str(tools_pex_file)?
                ),
                "build",
                "--dest-dir",
                path_as_str(&scie_pikesquares_package_dir)?,
                "--use-platform-suffix",
                "--hash",
                "sha256",
                path_as_str(&scie_pikesquares_manifest)?,
            ])
            .current_dir(&build_context.workspace_root),
    )?;
    let exe_full_name = binary_full_name(BINARY);
    Ok(SciePikeSquaresBuild {
        exe: scie_pikesquares_package_dir.join(exe_full_name.clone()),
        sha256: scie_pikesquares_package_dir.join(format!("{exe_full_name}.sha256")),
    })
}
