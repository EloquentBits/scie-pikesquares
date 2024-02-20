use std::path::Path;

use anyhow::{Context, Result};
use logging_timer::time;
use serde::Deserialize;

use crate::build_root::BuildRoot;

#[derive(Default, Deserialize)]
pub(crate) struct Global {
    #[serde(default)]
    pub(crate) pikesquares_version: Option<String>,
}

#[derive(Default, Deserialize)]
pub(crate) struct DebugPy {
    pub(crate) version: Option<String>,
}

#[derive(Default, Deserialize)]
pub(crate) struct Default {
    pub(crate) delegate_bootstrap: Option<bool>,
}

#[derive(Deserialize)]
pub(crate) struct Config {
    #[serde(default, rename = "GLOBAL")]
    pub(crate) global: Global,
    #[serde(default)]
    pub(crate) debugpy: DebugPy,
    #[serde(default, rename = "DEFAULT")]
    pub(crate) default: Default,
}

pub(crate) struct PikeSquaresConfig {
    build_root: BuildRoot,
    pub(crate) config: Config,
}

impl PikeSquaresConfig {
    pub(crate) fn package_version(&self) -> Option<String> {
        self.config.global.pikesquares_version.clone()
    }

    pub(crate) fn build_root(&self) -> &Path {
        self.build_root.as_path()
    }

    pub(crate) fn debugpy_version(&self) -> Option<String> {
        self.config.debugpy.version.clone()
    }

    pub(crate) fn delegate_bootstrap(&self) -> bool {
        self.config.default.delegate_bootstrap.unwrap_or_default()
    }
}

impl PikeSquaresConfig {
    #[time("debug", "PikeSquaresConfig::{}")]
    pub(crate) fn parse(build_root: BuildRoot) -> Result<PikeSquaresConfig> {
        let (pikesquares_config, provenance) = if let Some(path) = std::env::var_os("PIKESQUARES_TOML") {
            (path.into(), " (via PIKESQUARES_TOML env var)")
        } else {
            (build_root.join("pikesquares.toml"), "")
        };
        let contents = std::fs::read_to_string(&pikesquares_config).with_context(|| {
            format!(
                "Failed to read PikeSquares config from {path}{provenance}",
                path = pikesquares_config.display()
            )
        })?;
        let config: Config = toml::from_str(&contents).with_context(|| {
            format!(
                "Failed to parse PikeSquares config from {path}{provenance}",
                path = pikesquares_config.display()
            )
        })?;
        Ok(PikeSquaresConfig { build_root, config })
    }
}
