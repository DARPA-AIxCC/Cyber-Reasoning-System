use crate::challenge_project_description::ChallengeProjectDescription;
use crate::project_yaml_description::extract_metadata;
use sanitise_file_name::sanitise;
use std::fs::read_to_string;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

pub fn get_output_dir(destination_path: &Path) -> PathBuf {
    let mut destination_path = destination_path.to_path_buf();
    destination_path.push("benchmark");
    destination_path.push("darpa");
    destination_path
}

pub fn sanitise_directory_name(s: &str) -> String {
    sanitise(s).to_lowercase().replace(' ', "_")
}

/// Retrieves all challenges available under the given path
pub fn get_challenges(parent_path: &PathBuf) -> Vec<(PathBuf, ChallengeProjectDescription)> {
    let project_files: Vec<_> = WalkDir::new(parent_path)
        .into_iter()
        .flatten()
        .filter(|entry| entry.file_name().eq_ignore_ascii_case("project.yaml"))
        .collect();

    project_files
        .iter()
        .filter_map(|file| {
            let file_path = file.path();
            let yaml_input = read_to_string(file_path).ok()?;
            let raw_metadata = extract_metadata(yaml_input.as_str()).ok()?;
            let metadata = ChallengeProjectDescription::try_from(raw_metadata).ok()?;
            let parent_dir = file_path.parent()?;
            Some((parent_dir.to_path_buf(), metadata))
        })
        .collect::<Vec<_>>()
}
