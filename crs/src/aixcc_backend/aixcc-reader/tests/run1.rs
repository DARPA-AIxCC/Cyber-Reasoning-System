use assert_cmd::prelude::*; // Add methods on commands
use predicates::prelude::*; // Used for writing assertions
use std::process::Command; // Run programs

#[test]
fn test_set1() -> Result<(), Box<dyn std::error::Error>> {
    let mut cmd = Command::cargo_bin("aixcc-reader")?;

    // Assume that some of the arguments are set via environment, i.e. Docker/Kubernetes
    cmd.env("AIXCC_CP_ROOT", "tests/set1/")
        .env("AIXCC_CRS_SCRATCH_SPACE", "tests/set1_output/")
        .arg("--template-path=cerberus_configuration/cerberus.template")
        .arg("--default-config=cerberus_configuration/defaults.ini")
        .assert()
        .stdout(predicate::str::contains("Success"));

    Ok(())
}
