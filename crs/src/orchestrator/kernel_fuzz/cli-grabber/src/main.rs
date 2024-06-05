use std::env;
use std::fs::File;
use std::io::{Read, Write};
use std::path::Path;

use anyhow::{anyhow, Result};

fn try_read_for_token(p: &Path) -> Result<bool> {
    let token = "HEALING TOUCH SPECIAL";
    let n = 64;
    if p.exists() {
        let mut f = File::open(p)?;
        let mut buffer = vec![0; n];

        // Read the first N bytes
        f.read_exact(&mut buffer)?;

        // Convert the bytes to a string and check for the token
        let content = String::from_utf8_lossy(&buffer);
        eprintln!("{}", content);

        if (content.contains(token)) {
            return Ok(true);
        }
    }
    return Ok(false);
}

fn main() -> Result<()> {
    eprintln!("<CLI GRABBER>");
    // let mut of = File::create("/out/cli-grabber.txt")?;
    // writeln!(of, "<CLI GRABBER>");

    let mut args: Vec<String> = env::args().collect();

    let mut idx = 0;

    for i in 1..args.len() {
        let p = Path::new(&args[i]);
        match try_read_for_token(p) {
            Ok(true) => idx = i,
            _ => (),
        };
    }

    args.iter_mut().for_each(|a| *a = format!("\"{}\"", a));

    let cwd = env::current_dir().map(|p| p.display().to_string()).ok();

    if idx == 0 {
        eprintln!("HEALING TOUCH TOKEN NOT FOUND");
        // writeln!(of, "HEALING TOUCH TOKEN NOT FOUND");
    }
    let cwd = cwd.unwrap_or("None".to_owned());
    eprintln!(
        "<CLI GRABBER JSON> {{ \"cmd\": [{}], \"idx\": {}, \"cwd\": \"{}\" }}",
        args.join(", "),
        idx,
        cwd
    );

    // writeln!(
    //     of,
    //     "{{ \"cmd\": [{}], \"idx\": {}, \"cwd\": \"{}\" }}",
    //     args.join(", "),
    //     idx,
    //     cwd
    // )?;
    Ok(())
}
