//! Description of the project used across other components

use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Serialize, Debug)]
pub struct ChallengeProjectDescription {
    /// Name of the project
    pub cp_name: String,

    /// Main language used by the project
    pub language: Language,

    /// Pre-built address URL for Docker image
    pub docker_image: Option<String>,

    /// Set of sources required
    pub cp_sources: Vec<SourceEntry>,

    /// Sanitizers
    pub sanitizers: BTreeMap<SanitizerId, String>,

    /// Harnesses available
    pub harnesses: BTreeMap<HarnessId, HarnessEntry>,
}

/// Supported languages
#[derive(Serialize, Debug)]
pub enum Language {
    C,
    Java,
}

#[derive(Serialize, Ord, Eq, PartialOrd, PartialEq, Debug)]
pub struct SanitizerId(pub String);

#[derive(Serialize, Ord, Eq, PartialOrd, PartialEq, Debug)]
pub struct HarnessId(pub String);

/// Description of a harness
#[derive(Serialize, Debug)]
pub struct HarnessEntry {
    /// Name of the harness
    pub name: String,

    /// Path to source code of harness, if available
    pub source: Option<String>,

    /// Path to binary of harness, if available
    pub binary: Option<String>,
}

/// Description of the source code entry
#[derive(Serialize, Debug)]
pub struct SourceEntry {
    /// Url of the repository
    pub address: String,

    /// Tag, SHA, ... of the repository
    pub source_ref: Option<String>,

    /// Local path to the directory of the source
    pub path: String,

    /// Relative paths to artifacts
    pub artifacts: Option<Vec<String>>,
}
