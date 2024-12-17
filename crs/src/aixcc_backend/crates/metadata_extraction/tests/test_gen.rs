//! Tests provided project descriptions.
//!
//! Reads all YAML files in the `tests/*.yaml` directory,
//! generates the JSON description and compares it
//! with the expected output described by `tests/*.out`
use glob::glob;
use metadata_extraction::challenge_project_description::ChallengeProjectDescription;
use metadata_extraction::project_yaml_description::extract_metadata;
use std::fs::read_to_string;

pub type Result<T> = core::result::Result<T, Error>;
pub type Error = Box<dyn std::error::Error>;
#[test]
fn test_inputs() -> Result<()> {
    for e in glob("./tests/project-input/*.yaml").map_err(|e| format!("Pattern error {e}"))? {
        let yaml_file = e.map_err(|e| format!("Pattern error {e}"))?;
        let out_file = yaml_file.with_extension("out");

        let yaml_input = read_to_string(yaml_file.as_os_str())?;
        let raw_metadata = extract_metadata(yaml_input.as_str())?;
        let metadata = ChallengeProjectDescription::try_from(raw_metadata)?;
        let output =
            serde_json::to_string_pretty(&metadata).map_err(|e| format!("Serde JSON error {e}"))?;

        let expected_output = read_to_string(out_file)?;

        assert_eq!(output, expected_output)
    }

    Ok(())
}
