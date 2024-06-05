use crate::error::Result;

use serde::Serialize;
use std::path::PathBuf;
use tera::{Context, Tera};
use tera_text_filters::register_all;

/// This function takes a template file and instance data, instantiates the template with that data, and returns the resulting text as a string.
pub fn instantiate_template(
    template_file: PathBuf,
    instance_data: impl Serialize,
    default_data: impl Serialize,
) -> Result<String> {
    let mut template_engine = Tera::default();
    register_all(&mut template_engine);
    template_engine
        .add_template_file(template_file, Some("template"))
        .map_err(|e| format!("Template reading error: {e:?}"))?;

    // Use different data sources
    let mut context = Context::from_serialize(&instance_data)
        .map_err(|e| format!("Template context error: {e:?}"))?;

    let default_context = Context::from_serialize(default_data)
        .map_err(|e| format!("Template context error: {e:?}"))?;
    context.extend(default_context);

    let output = template_engine
        .render("template", &context)
        .map_err(|e| format!("Template render error: {e:?}"))?;
    Ok(output)
}
