use clap::Parser;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[clap(version, about)]
pub struct Arguments {
    #[clap(env = "AIXCC_API_HOSTNAME")]
    directory: PathBuf,

    /// Provide destination directory where to write different configurations
    #[clap(env = "AIXCC_CRS_SCRATCH_SPACE")]
    destination_directory: PathBuf,
}
