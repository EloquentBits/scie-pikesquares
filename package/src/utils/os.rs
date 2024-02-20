#[cfg(windows)]
pub(crate) const PATHSEP: &str = ";";

#[cfg(windows)]
pub(crate) const EOL: &str = "\r\n";

#[cfg(unix)]
pub(crate) const PATHSEP: &str = ":";

#[cfg(unix)]
pub(crate) const EOL: &str = "\n";
