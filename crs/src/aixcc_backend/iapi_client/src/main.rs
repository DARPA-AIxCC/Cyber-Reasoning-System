use clap::{Parser, Subcommand};
use lib_iapi::client;
use reqwest::Url;
use std::env;
use std::path::PathBuf;
use tokio::fs::File;
use tokio::io::{AsyncReadExt, BufReader};

pub type Result<T> = core::result::Result<T, Error>;
pub type Error = Box<dyn std::error::Error>;

/// A fictional versioning CLI
#[derive(Debug, Parser)] // requires `derive` feature
#[command(name = "iapi-client")]
#[command(about = "iAPI CLI tool to communicate with the iAPI web services", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    /// Checks the health of the iAPI service
    #[command(arg_required_else_help = true)]
    Health,

    /// Submit discovered vulnerability
    #[command(arg_required_else_help = true)]
    SubmitVulnerability {
        /// Name of the Challenge Project (CP)
        #[clap(long)]
        #[arg(required = true)]
        cp_name: String,

        /// Sanitizer ID
        #[clap(long)]
        #[arg(required = true)]
        sanitizer_id: String,

        /// Commit SHA1
        #[clap(long)]
        #[arg(required = true)]
        commit_sha1: String,

        /// Harness ID
        #[clap(long)]
        #[arg(required = true)]
        harness_id: String,

        /// Path to harness input
        #[clap(long)]
        #[arg(required = true)]
        harness_input: PathBuf,
    },

    /// Submit generated patch for previously submitted discovered vulnerability
    SubmitGeneratedPatch {
        /// UUID of vulnerability discovery
        #[clap(long)]
        #[arg(required = true)]
        vds_uuid: String,

        /// Path to patch
        #[clap(long)]
        #[arg(required = true)]
        patch_file: PathBuf,
    },

    /// Checks status of given vulnerability
    CheckVulnerabilityStatus {
        /// UUID of vulnerability discovery
        vds_uuid: String,
    },

    /// Checks status of given patch
    CheckPatchAcceptanceStatus {
        /// UUID of patch submission
        pg_uuid: String,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let binding = env::var_os("AIXCC_API_HOSTNAME");

    let address = binding
        .as_ref()
        .and_then(|os| os.to_str())
        .ok_or("Invalid address in AIXCC_API_HOSTNAME")?;

    let address = Url::parse(address)?;

    let args = Cli::parse();
    match args.command {
        Commands::Health => {
            let result = lib_iapi::client::check_health(&address).await?;
            println!("{result}");
        }
        Commands::SubmitVulnerability {
            cp_name,
            sanitizer_id,
            commit_sha1,
            harness_id,
            harness_input,
        } => {
            let file = File::open(harness_input).await?;
            let mut buffer = BufReader::new(file);

            let mut harness_input_content = String::new();
            buffer.read_to_string(&mut harness_input_content).await?;

            let result = client::submit_proof_of_vulnerability_discovery(
                &address,
                cp_name,
                sanitizer_id,
                commit_sha1,
                harness_id,
                harness_input_content,
            )
            .await?;
            println!("{result}")
        }
        Commands::SubmitGeneratedPatch {
            vds_uuid,
            patch_file,
        } => {
            let file = File::open(patch_file).await?;
            let mut buffer = BufReader::new(file);

            let mut patch_content = String::new();
            buffer.read_to_string(&mut patch_content).await?;

            let result = client::submit_generated_patch(&address, vds_uuid, patch_content).await?;
            println!("{result:?}")
        }
        Commands::CheckVulnerabilityStatus { vds_uuid } => {
            let result = client::check_vulnerability_discovery_status(&address, vds_uuid).await?;
            println!("{result:?}");
        }
        Commands::CheckPatchAcceptanceStatus { pg_uuid } => {
            let result = client::check_generated_patch_status(&address, pg_uuid).await?;
            println!("{result:?}");
        }
    }

    Ok(())
}
