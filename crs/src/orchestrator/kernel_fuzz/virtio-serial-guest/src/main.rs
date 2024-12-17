use std::fs::File;
use std::io::{Read, Write};
use std::os::fd::{AsRawFd, FromRawFd};
use std::path::PathBuf;
use std::process::Command;

use anyhow::Result;
use clap::Parser;

#[derive(clap::Parser, Debug)]
#[clap(version, about, long_about = None)]
pub struct Args {
	/// Path to the unix domain socket to connect to
	#[clap(short, long, name = "SOCKET", default_value = "/dev/virtio-ports/aflControl")]
	socket: PathBuf,

	/// Path to the input file to be overwritten
	#[clap(short, long, name = "INPUT FILE")]
	input_file: PathBuf,

	/// Send `dmesg` output back to host on termination
	#[clap(short, name = "DMESG")]
	dmesg: bool,

	/// Sleep after termination to e.g. avoid exiting VM
	#[clap(short, name = "BLOCK_UNTIL_SNAPSHOT", default_value = "true")]
	block_until_snapshot: bool,

	/// Command to run after receiving input
	#[clap(name = "COMMAND", trailing_var_arg = true)]
	command_with_args: Vec<String>,
}

#[derive(Debug)]
struct NakedFile(std::os::fd::OwnedFd);

impl std::io::Read for NakedFile {
	fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
		nix::unistd::read(self.0.as_raw_fd(), buf).map_err(std::io::Error::from)
	}
}

impl std::io::Write for NakedFile {
	fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
		nix::unistd::write(&self.0, buf).map_err(std::io::Error::from)
	}

	fn flush(&mut self) -> std::io::Result<()> {
		// Flushing is a no-op, as we immediately perform every read/write.
		Ok(())
	}
}

const MSG_SIZE_BYTES: u32 = 4;
const BUF_SIZE: usize = 4096;

fn recv<R: Read>(stream: &mut R) -> Result<Vec<u8>> {
	let mut response = Vec::new();

	let mut msg_size: Option<u32> = None;
	let mut total_bytes_read: u32 = 0;

	loop {
		let mut buf = [0u8; BUF_SIZE];
		let bytes_read = stream.read(&mut buf)?;
		total_bytes_read += bytes_read as u32;

		if bytes_read == 0 {
			break;
		} else if msg_size.is_none() && total_bytes_read >= MSG_SIZE_BYTES {
			msg_size = Some(u32::from_le_bytes(buf[..4].try_into().unwrap()));
			response.extend_from_slice(&buf[4..bytes_read]);
		} else {
			response.extend_from_slice(&buf[..bytes_read]);
		}

		if msg_size.is_some_and(|s| response.len() == s as usize) {
			break;
		}

		assert!(!msg_size.is_some_and(|s| (s as usize) < response.len()));
	}

	Ok(response)
}

fn send<W: Write>(stream: &mut W, msg: &[u8]) -> Result<()> {
	// @TODO probably faster as a single write
	stream.write_all(&u32::to_le_bytes(msg.len() as u32)[..])?;
	stream.write_all(msg)?;
	stream.flush()?;
	println!("<GUEST> sent {} bytes", msg.len());
	return Ok(());
}

fn main() -> anyhow::Result<()> {
	let args = Args::parse();

	let subcmd = &args.command_with_args[0];
	let subcmd_args = &args.command_with_args[1..];

	let mut cmd = Command::new(subcmd);
	let cmd = cmd.args(subcmd_args);

	println!("<GUEST> Opening connection...");
	let mut host_fd = NakedFile(unsafe {
		std::os::fd::OwnedFd::from_raw_fd(nix::fcntl::open(
			&args.socket,
			nix::fcntl::OFlag::O_RDWR,
			nix::sys::stat::Mode::empty(),
		)?)
	});

	let mut file = File::create(&args.input_file)?;

	send(&mut host_fd, b"Snapshot me!")?;

	println!("<GUEST> Waiting for program input...");
	let input = recv(&mut host_fd)?;
	file.write_all(&input[..])?;
	println!("<GUEST> Beginning execution...");

	let mut child = cmd.spawn()?;
	let _ecode = child.wait()?;

	if args.dmesg {
		let mut cmd = Command::new("dmesg");
		let dmesg_out = cmd.output()?.stdout;
		send(&mut host_fd, &dmesg_out[..])?;
	} else {
		send(&mut host_fd, b"Restore me!")?;
	}

	if args.block_until_snapshot {
		println!("<GUEST> Waiting for snapshot...");
		std::thread::sleep(std::time::Duration::from_secs(100));
	}

	Ok(())
}
