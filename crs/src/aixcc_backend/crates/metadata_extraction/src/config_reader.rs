//! Provides a reader to load configuration
use crate::error::Result;
use std::collections::HashMap;

pub fn get_configuration(basename: &str) -> Result<HashMap<String, String>> {
    // Add configuration values from a file named `configuration`.
    // It will look for any top-level file with an extension
    // that `config` knows how to parse: yaml, json, etc.

    let config = config::Config::builder().add_source(config::File::with_name(basename));

    match config.build() {
        Ok(c) => Ok(c
            .try_deserialize::<HashMap<String, String>>()
            .map_err(|e| format!("Couldn't read configuration: {e:?}"))?),
        Err(e) => Err(format!("Config error: {e:?}").into()),
    }
}
