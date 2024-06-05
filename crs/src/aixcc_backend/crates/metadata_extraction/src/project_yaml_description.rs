//! Handle different types of `project.yaml` files and creates
//! project description that can be used in later steps
use crate::challenge_project_description::{
    ChallengeProjectDescription, HarnessEntry, HarnessId, SanitizerId,
};
use crate::error::Error;
use crate::{challenge_project_description, error};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Deserialize, Serialize, PartialEq, Debug, Default)]
pub struct ProjectDescriptionRaw {
    /// Name of the project
    #[serde(default)]
    cp_name: Option<String>,

    /// Target language used by the project
    // #[serde(default, deserialize_with="from_lang_string")]
    language: Option<Language>,

    /// Address of the full challenge project's repository
    #[serde(default)]
    cp_address: Option<String>,

    /// Source code addresses
    cp_sources: Option<BTreeMap<String, SourceEntryRaw>>,

    /// Source code address: maps id to source origin
    /// TODO: This is essentially `cp_sources` without the proper mapping for the target directory, find a better path
    cp_source_address: Option<BTreeMap<String, String>>,

    /// Pre-built docker image base
    #[serde(alias = "docker_img_address")]
    docker_image: Option<MaybePath>,

    /// List of sanitizers available for this project
    sanitizers: Option<BTreeMap<String, Sanitizer>>,

    /// List of harnesses provided by this project
    harnesses: Option<BTreeMap<String, Harness>>,
}

#[derive(Deserialize, Serialize, PartialEq, Debug)]
struct SourceEntryRaw {
    /// Source code address
    address: String,

    /// Old version is string, replaced by `referenced_commit`
    directory: Option<String>,

    /// Referenced commit, if not provided will be main
    #[serde(alias = "ref")]
    referenced_commit: Option<String>,

    /// Artifacts available
    artifacts: Option<Vec<String>>,
}

#[derive(Deserialize, Serialize, Debug, PartialEq)]
#[serde(try_from = "String")]
enum Language {
    C,
    Java,
    Unknown(String),
}

impl TryFrom<String> for Language {
    type Error = Error;

    fn try_from(value: String) -> error::Result<Self> {
        match value.to_uppercase().as_str() {
            "C" => Ok(Language::C),
            "JAVA" => Ok(Language::Java),
            _ => Ok(Language::Unknown(value.to_string())),
        }
    }
}

#[derive(Deserialize, Serialize, Debug, PartialEq)]
#[serde(try_from = "String")]
struct Sanitizer(String);

impl TryFrom<String> for Sanitizer {
    type Error = Error;

    fn try_from(value: String) -> core::result::Result<Self, Self::Error> {
        Ok(Sanitizer(value))
    }
}

#[derive(Deserialize, Serialize, Debug, PartialEq)]
struct Harness {
    /// Name if the harness
    name: Option<String>,

    /// Path to source of harness
    source: Option<MaybePath>,

    /// Path to binary of harness, if available
    binary: Option<MaybePath>,
}

/// Describes a path if available, otherwise NoPath
#[derive(Serialize, Deserialize, Debug, PartialEq)]
#[serde(try_from = "String")]
pub enum MaybePath {
    NoPath,
    Path(String),
}

impl TryFrom<String> for MaybePath {
    type Error = Error;

    fn try_from(value: String) -> core::result::Result<Self, Self::Error> {
        match value.to_uppercase().as_str() {
            "N/A" => Ok(MaybePath::NoPath),
            _ => Ok(MaybePath::Path(value.to_string())),
        }
    }
}

pub fn extract_metadata(content: &str) -> error::Result<ProjectDescriptionRaw> {
    serde_yaml::from_str(content).map_err(|e| format!("Content Error {e}").into())
}

#[derive(Debug)]
pub enum ParsingError {
    ContentError(String),
}

/// Converts the raw project description in a challenge project description
impl TryFrom<ProjectDescriptionRaw> for ChallengeProjectDescription {
    type Error = Error;

    fn try_from(project_description: ProjectDescriptionRaw) -> core::result::Result<Self, Error> {
        let cp_name = project_description.cp_name.ok_or("No cp name provided")?;

        let language = match project_description.language.ok_or("No language provided")? {
            Language::C => challenge_project_description::Language::C,
            Language::Java => challenge_project_description::Language::Java,
            Language::Unknown(lang) => {
                return Err(format!("Unsupported language: {lang}").into());
            }
        };

        let docker_image = match project_description
            .docker_image
            .ok_or("No docker path provided")?
        {
            MaybePath::NoPath => None,
            MaybePath::Path(path) => Some(path),
        };

        let sanitizers = project_description
            .sanitizers
            .ok_or("No sanitizers provided")?
            .iter()
            .map(|(id, sanitizer)| {
                let san_id = SanitizerId(id.clone());
                let description = sanitizer.0.clone();

                (san_id, description)
            })
            .collect();

        let harnesses: error::Result<BTreeMap<_, _>> = project_description
            .harnesses
            .ok_or("No harnesses provided")?
            .iter()
            .map(|(id, harness)| {
                let harn_id = HarnessId(id.clone());

                // If no name provided, re-use the harness ID as name
                let name = harness.name.as_ref().unwrap_or(id).to_string();

                let source = match harness.source.as_ref().ok_or("Source error")? {
                    MaybePath::NoPath => None,
                    MaybePath::Path(path) => Some(path.clone()),
                };

                let binary = match harness.binary.as_ref().ok_or("Binary error")? {
                    MaybePath::NoPath => None,
                    MaybePath::Path(path) => Some(path.clone()),
                };

                Ok((
                    harn_id,
                    HarnessEntry {
                        name,
                        source,
                        binary,
                    },
                ))
            })
            .collect();

        let cp_sources = if let Some(entries) = project_description.cp_sources {
            entries
                .iter()
                .map(|(id, raw_source_entry)| {
                    let path = raw_source_entry
                        .directory
                        .as_deref()
                        .unwrap_or(id.as_str())
                        .to_string();
                    let artifacts = raw_source_entry.artifacts.as_ref().map(|a| a.to_vec());
                    challenge_project_description::SourceEntry {
                        address: raw_source_entry.address.clone(),
                        source_ref: Some(
                            raw_source_entry
                                .referenced_commit
                                .clone()
                                .unwrap_or("main".to_string())
                                .to_string(),
                        ),
                        path,
                        artifacts,
                    }
                })
                .collect()
        } else if let Some(entries) = project_description.cp_source_address {
            entries
                .iter()
                .map(
                    |(path, address)| challenge_project_description::SourceEntry {
                        address: address.clone(),
                        source_ref: Some("main".to_string()),
                        path: path.clone(),
                        artifacts: None,
                    },
                )
                .collect()
        } else {
            vec![]
        };

        Ok(ChallengeProjectDescription {
            cp_name,
            language,
            docker_image,
            cp_sources,
            sanitizers,
            harnesses: harnesses?,
        })
    }
}

#[cfg(test)]
mod test {
    use crate::error::Result;
    use crate::project_yaml_description::{
        Harness, Language, MaybePath, ProjectDescriptionRaw, Sanitizer, SourceEntryRaw,
    };
    use std::collections::BTreeMap;

    #[test]
    fn test_name() -> Result<()> {
        let yaml = r#"
cp_name: "foo"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                cp_name: Some("foo".to_string()),
                ..Default::default()
            }
        );
        Ok(())
    }

    #[test]
    fn test_language_c() -> Result<()> {
        let yaml = r#"
language: "C"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                language: Some(Language::C),
                ..Default::default()
            }
        );

        let yaml = r#"
language: "c"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                language: Some(Language::C),
                ..Default::default()
            }
        );

        Ok(())
    }

    #[test]
    fn test_language_java() -> Result<()> {
        let yaml = r#"
language: "java"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                language: Some(Language::Java),
                ..Default::default()
            }
        );

        let yaml = r#"
language: "Java"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                language: Some(Language::Java),
                ..Default::default()
            }
        );
        Ok(())
    }
    #[test]
    fn test_unknown_language() -> Result<()> {
        let yaml = r#"
language: "boo"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                language: Some(Language::Unknown("boo".to_string())),
                ..Default::default()
            }
        );
        Ok(())
    }

    #[test]
    fn test_cp_address() -> Result<()> {
        let yaml = r#"
cp_address: "git@github.com:project/address.git"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                cp_address: Some("git@github.com:project/address.git".to_string()),
                ..Default::default()
            }
        );
        Ok(())
    }

    #[test]
    fn test_cp_sources() -> Result<()> {
        let yaml = r#"
cp_sources:
  proj1:
    address: "git@github.com:project/source1.git"
    directory: ".readonly/source1"
  plugins/proj1-foo-plugin:
    address: "git@github.com:project/source2.git"
    directory: ".readonly/project2"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;

        let expected_sources: BTreeMap<String, SourceEntryRaw> = BTreeMap::from([
            (
                "proj1".to_string(),
                SourceEntryRaw {
                    address: "git@github.com:project/source1.git".to_string(),
                    directory: Some(".readonly/source1".to_string()),
                    referenced_commit: None,
                    artifacts: None,
                },
            ),
            (
                "plugins/proj1-foo-plugin".to_string(),
                SourceEntryRaw {
                    address: "git@github.com:project/source2.git".to_string(),
                    directory: Some(".readonly/project2".to_string()),
                    referenced_commit: None,
                    artifacts: None,
                },
            ),
        ]);
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                cp_sources: Some(expected_sources),
                ..Default::default()
            }
        );
        Ok(())
    }

    #[test]
    fn test_cp_sources_artifacts() -> Result<()> {
        let yaml = r#"
cp_sources:
  proj1:
    address: "git@github.com:project/source1.git"
    ref: v1.0.0
    artifacts:
      - src/to/final/obj
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;

        let expected_sources: BTreeMap<String, SourceEntryRaw> = BTreeMap::from([(
            "proj1".to_string(),
            SourceEntryRaw {
                address: "git@github.com:project/source1.git".to_string(),
                directory: None,
                referenced_commit: Some("v1.0.0".into()),
                artifacts: Some(vec!["src/to/final/obj".into()]),
            },
        )]);
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                cp_sources: Some(expected_sources),
                ..Default::default()
            }
        );
        Ok(())
    }

    #[test]
    fn test_docker_image() -> Result<()> {
        let yaml = r#"
docker_image: "ghcr.io/aixcc/docker1:v1.0.0"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                docker_image: Some(MaybePath::Path("ghcr.io/aixcc/docker1:v1.0.0".to_string())),
                ..Default::default()
            }
        );

        Ok(())
    }

    #[test]
    fn test_sanitizers() -> Result<()> {
        let yaml = r#"
sanitizers:
  id_1: "OsCommandinjection"
  id_2: "foo"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;

        let expected_sanitizers: BTreeMap<String, Sanitizer> = BTreeMap::from([
            ("id_1".to_string(), Sanitizer("OsCommandinjection".into())),
            ("id_2".to_string(), Sanitizer("foo".to_string())),
        ]);
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                sanitizers: Some(expected_sanitizers),
                ..Default::default()
            }
        );

        let yaml = r#"
sanitizers:
  id_1: "KASAN: slab-out-of-bounds"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;

        let expected_sanitizers: BTreeMap<String, Sanitizer> = BTreeMap::from([(
            "id_1".to_string(),
            Sanitizer("KASAN: slab-out-of-bounds".into()),
        )]);
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                sanitizers: Some(expected_sanitizers),
                ..Default::default()
            }
        );
        Ok(())
    }

    #[test]
    fn test_harnesses() -> Result<()> {
        let yaml = r#"
harnesses:
  harness_id_1:
    name: test_harness_id_1
    source: "c_script/harness1.java"
    binary: "n/a"
"#;
        let example1: ProjectDescriptionRaw = serde_yaml::from_str(yaml)?;

        let expected_harnesses: BTreeMap<String, Harness> = BTreeMap::from([(
            "harness_id_1".to_string(),
            Harness {
                name: Some("test_harness_id_1".into()),
                source: Some(MaybePath::Path("c_script/harness1.java".into())),
                binary: Some(MaybePath::NoPath),
            },
        )]);
        assert_eq!(
            example1,
            ProjectDescriptionRaw {
                harnesses: Some(expected_harnesses),
                ..Default::default()
            }
        );
        Ok(())
    }
}
