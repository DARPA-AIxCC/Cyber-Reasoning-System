//! Tests the instantiation of templates
//!
//! Reads all `*.template` files in the `templating` directory and the respective project description
//! from the respective `.yaml` file. The template is instantiated with the description and the generated output compared with the expected content from the `.out` file.

use glob::glob;
use metadata_extraction::challenge_project_description::ChallengeProjectDescription;
use metadata_extraction::config_reader::get_configuration;
use metadata_extraction::project_yaml_description::extract_metadata;
use metadata_extraction::templating;
use std::fs::read_to_string;

pub type Result<T> = core::result::Result<T, Error>;
pub type Error = Box<dyn std::error::Error>;
#[test]
fn test_template_instantiation() -> Result<()> {
    let defaults = get_configuration("./tests/templating/defaults.ini")?;

    for e in glob("./tests/templating/*.template").map_err(|e| format!("Pattern error {e}"))? {
        let template_file = e.map_err(|e| format!("Pattern error {e}"))?;

        let project_input_file = template_file.with_extension("yaml");
        let expected_output_file = template_file.with_extension("out");
        let expected_output = read_to_string(expected_output_file.as_os_str())
            .map_err(|e| format!("Error: {e} for {expected_output_file:?}"))?;

        let yaml_input = read_to_string(project_input_file.as_os_str())
            .map_err(|e| format!("Not found {e} for {project_input_file:?}"))?;
        let metadata =
            ChallengeProjectDescription::try_from(extract_metadata(yaml_input.as_str())?)?;

        // let defaults = HashMap::from([("unknown", "**UNKNOWN**")]);

        println!("Read metadata {metadata:#?}");
        let output =
            templating::instantiate_template(template_file, &metadata, Some(defaults.clone()))?;
        println!("Output {output}");

        assert_eq!(output, expected_output)
    }

    Ok(())
}
