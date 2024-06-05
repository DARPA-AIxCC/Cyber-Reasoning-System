use clap::Parser;
use metadata_extraction::challenge_project_description::Language;
use metadata_extraction::config_reader::get_configuration;
use metadata_extraction::error::Result;
use metadata_extraction::templating::instantiate_template;
use rayon::prelude::*;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::{env, fs};
use tracing::info;
use tracing::level_filters::LevelFilter;
use tracing_subscriber::EnvFilter;
#[derive(Parser, Debug)]
#[clap(version, about)]
/// Parses AIxCC challenge project descriptions and provides different output formats.
struct Arguments {
    #[clap(env = "AIXCC_CP_ROOT")]
    directory: PathBuf,

    #[clap(short, long)]
    /// Path to the template file that should be used for generating the output
    template_path: PathBuf,

    /// Use the provided config file to populate missing template values
    #[clap(short, long)]
    default_config: PathBuf,

    /// Provide destination directory where to write different configurations
    #[clap(env = "AIXCC_CRS_SCRATCH_SPACE")]
    destination_directory: PathBuf,
}

fn copy_dir(src: &PathBuf, dst: &PathBuf) -> Result<()> {
    fs::create_dir_all(dst)?;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let path = entry.path();
        let file_name = path.file_name().ok_or("Incorrect filename")?;
        let target_file = dst.join(file_name);
        if entry.file_type()?.is_dir() {
            //info!("Copying dir {path:#?}");
            fs::create_dir_all(&target_file)?;
            copy_dir(&path, &target_file)?;
        } else if entry.file_type()?.is_file() {
            //info!("Copying file {path:#?}");
            fs::copy(path, target_file)?;
        } else {
            //info!("Skipping entry: {entry:?}");
            let _entry_type = entry.file_type()?;
            //info!("Entry type: {entry_type:?}");
        }
    }
    Ok(())
}

fn main() -> Result<()> {
    // Set logging to INFO
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::builder()
                .with_default_directive(LevelFilter::INFO.into())
                .from_env_lossy(),
        )
        .init();

    let args = Arguments::parse();

    args.default_config
        .try_exists()
        .map_err(|e| format!("Provided default config path does not exist: {e:?}"))?;
    let path = args.default_config.to_str().ok_or("Wrong path")?;

    let mut default_config = get_configuration(path)?;
    // Populate default config with AIXCC environment variables
    for (key, value) in env::vars() {
        if key.starts_with("AIXCC_") {
            default_config.insert(key, value);
        }
    }
    //info!("CONFIG: {default_config:?}");

    let template = args.template_path;
    template.try_exists()?;

    let destination_path = metadata_extraction::fs::get_output_dir(&args.destination_directory);

    let project_descriptions = metadata_extraction::fs::get_challenges(&args.directory);

    project_descriptions
        .par_iter()
        .map(|(parent_dir, metadata)| {
            let sanitised_name =
                metadata_extraction::fs::sanitise_directory_name(metadata.cp_name.as_str());

            let mut default_config = default_config.clone();
            default_config.insert("cp_sanitized".into(), sanitised_name.clone());

            if metadata.cp_name.to_lowercase().contains("linux") {
                if let Some(_artifact) = metadata.cp_sources[0]
                    .artifacts
                    .as_ref()
                    .and_then(|entries| entries.first())
                {
                    default_config.insert(
                        "binary_override".into(),
                        "src/linux_kernel/vmlinux".to_string(),
                    );
                }
            }

            let output = instantiate_template(template.clone(), metadata, default_config)?;

            let mut target_dir = destination_path.clone();
            target_dir.push(&sanitised_name);

            // Create output directory:
            fs::create_dir_all(&target_dir)?;

            let mut target_file = target_dir.clone();
            target_file.push("meta-data.json");

            // Write generated content to target file
            fs::write(target_file, output)?;

            let parent = args.default_config.parent().unwrap_or(Path::new("./"));
            let template_script_dir = parent.join(match metadata.language {
                Language::C => {
                    if metadata.cp_name.to_lowercase().contains("linux") {
                        "kernelspace_scripts"
                    } else {
                        "userspace_scripts"
                    }
                }
                Language::Java => "java_scripts",
            });
            let workflow_path = parent.join(match metadata.language {
                Language::C => {
                    if metadata.cp_name.to_lowercase().contains("linux") {
                        "kernelspace_workflow.json"
                    } else {
                        "userspace_workflow.json"
                    }
                }
                Language::Java => "java_workflow.json",
            });

            //info!("Workflow path: {workflow_path:?}");

            // Read workflow path and copy it to the target directory
            let workflow = fs::read_to_string(workflow_path)?;
            let mut target_file = target_dir.clone();
            target_file.push("workflow.json");
            fs::write(target_file, workflow)?;

            //info!("Template script dir: {template_script_dir:?}");

            metadata
                .harnesses
                .iter()
                .enumerate()
                .par_bridge()
                .map(|(i, (harness_id, harness_entry))| {
                    let harness_identifier = harness_id.0.clone();
                    let j = i + 1;
                    let id = format!("{harness_identifier}_{j}");
                    let mut target_dir = target_dir.clone();
                    target_dir.push(&id);

                    fs::create_dir_all(&target_dir)?;

                    let mut contents_parent = parent_dir.clone();
                    contents_parent.push(".");

                    //info!("Copying from {template_script_dir:?} to {target_dir:?}");

                    info!("Copying from {parent_dir:?} to {target_dir:?}");
                    let x = Command::new("rsync")
                        .arg("-azS")
                        .arg(contents_parent)
                        .arg(&target_dir)
                        .output()
                        .expect("failed to execute process");
                    info!("rsync output: {x:?}");

                    if x.status.success() {
                        info!("rsync success");
                    } else {
                        info!("rsync failed");
                        copy_dir(&parent_dir.to_path_buf(), &target_dir)?;
                    }

                    // Copy scripts to target directory
                    for entry in fs::read_dir(template_script_dir.clone())? {
                        //info!("Entry: {entry:?}");
                        let entry = entry?;
                        let path = entry.path();
                        let file_name = path.file_name().unwrap();

                        let mut target_file = target_dir.clone();

                        // Print target file
                        //info!("Target file: {target_file:?}");

                        target_file.push(file_name);
                        if entry.file_type()?.is_dir() {
                            //info!("Copying directory: {entry:#?} to {target_file:#?}");
                            copy_dir(&entry.path(), &target_file)?;
                        } else {
                            // Replace placeholders in scripts
                            let script = fs::read_to_string(entry.path())?;
                            let script = script
                                .replace("<SUBJECT>", &sanitised_name)
                                .replace("<ID>", &id)
                                .replace("<HARNESS_ID>", &harness_entry.name)
                                .replace("<HARNESS_PATH>", harness_entry.source.as_ref().unwrap())
                                .replace("<HARNESS_BINARY>", harness_entry.binary.as_ref().unwrap())
                                .replace(
                                    "<SANITIZERS>",
                                    &metadata
                                        .sanitizers
                                        .iter()
                                        .map(|x| "(".to_owned() + x.1.as_str() + ")")
                                        .collect::<Vec<String>>()
                                        .join("|"),
                                );

                            fs::write(&target_file, script)?;
                            fs::set_permissions(
                                &target_file,
                                fs::metadata(entry.path())?.permissions(),
                            )?;
                        }
                    }

                    let mut completion_file = target_dir.clone();
                    completion_file.push(".prepared");
                    fs::write(&completion_file, "done")?;

                    Ok(())
                })
                .for_each(|x: Result<()>| {
                    if let Err(e) = x {
                        info!("Error: {e:?}");
                    }
                });

            Ok(())
        })
        .for_each(|x: Result<()>| {
            if let Err(e) = x {
                info!("Error: {e:?}");
            }
        });

    info!("Success");
    Ok(())
}
