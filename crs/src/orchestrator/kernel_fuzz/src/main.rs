#![allow(dead_code)]

mod observer;

use crate::observer::kcov_map_observer::KcovMapObserver;
use kcovreader::DynamicKcov;
use libafl::corpus::{CachedOnDiskCorpus, Corpus, InMemoryCorpus, OnDiskCorpus};
use libafl::events::EventFirer;
use libafl::executors::ExitKind;
use libafl::executors::{Executor, HasObservers};
use libafl::feedbacks::{CrashFeedback, MaxMapFeedback, TimeoutFeedback};
use libafl::inputs::bytes::BytesInput;
use libafl::inputs::UsesInput;
use libafl::mutators::scheduled::{havoc_mutations, StdScheduledMutator};
use libafl::observers::{ObserversTuple, UsesObservers};
use libafl::prelude::{HasExecutions, HasTargetBytes, State, UsesState};
use libafl::schedulers::RandScheduler;
use libafl::stages::mutational::StdMutationalStage;
use libafl::state::{HasCorpus, StdState};
use libafl::Fuzzer;
use libafl::{feedback_and_fast, feedback_not};
use libafl::{Error, StdFuzzer};
use libafl_bolts::rands::StdRand;
use libafl_bolts::tuples::tuple_list;
use libafl_bolts::AsSlice;
use libafl_bolts::Named;
use log::debug;
use log::error;
use shared_memory::{Shmem, ShmemConf};
use std::fmt::Debug;
use std::fs;
use std::fs::File;
use std::marker::PhantomData;
use std::ops::Drop;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use walkdir::WalkDir;

use std::io::{BufRead, BufReader, BufWriter, Read, Write};
use std::os::unix::net::UnixStream;
use std::time::Duration;

use anyhow::{anyhow, Result};
use clap::Parser;

const SHM_SIZE: usize = 1048576;

const MSG_SIZE_BYTES: u32 = 4;
const BUF_SIZE: usize = 4096;

//parallel
use libafl::events::{launcher::Launcher, EventConfig};
use libafl::monitors::MultiMonitor;
use libafl_bolts::core_affinity::Cores;
use libafl_bolts::shmem::{ShMemProvider, StdShMemProvider};
//Grimoire
use libafl::mutators::grimoire::{
    GrimoireExtensionMutator, GrimoireRandomDeleteMutator, GrimoireRecursiveReplacementMutator,
    GrimoireStringReplacementMutator,
};
use libafl::observers::CanTrack;
use libafl::stages::generalization::GeneralizationStage;

//Monitor
use std::collections::HashSet;
use std::sync::{Arc, Mutex};
use std::thread;

/// LibAFL-KCOV
#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Args {
    /// QEMU Command JSON file
    #[arg(short, long)]
    qemu_command_json_file: PathBuf,

    /// Base port for QEMU monitor communication
    #[arg(short, long, default_value = "9192")]
    base_port: u16,

    /// Number of instances to run
    #[arg(short, long, default_value = "3")]
    num_instances: usize,

    /// Directory containing initial testcases
    #[arg(short, long)]
    initial_corpus: Vec<PathBuf>,

    /// Snapshot tag for QEMU monitor `savevm` and `loadvm`  
    #[arg(short = 'z', long, default_value = "start")]
    snapshot_tag: String,

    /// Tracing for SBFL  
    #[arg(short, long, default_value = "false")]
    trace_only: bool,

    /// Symbols file for debug symbolized traces
    #[arg(short, long)]
    symbols: Option<PathBuf>,

    /// Output directory for traces or crashes
    #[arg(short, long, default_value = "out")]
    output_dir: PathBuf,

    /// Directory for corpora used by fuzzers during campaign
    #[arg(short = 'c', long, default_value = "queue")]
    queue_dir: PathBuf,

    /// Use Grimoire mutators
    #[arg(long, default_value = "false")]
    use_grimoire: bool,

    /// Directory to monitor for new test cases
    #[arg(long)]
    monitor_dir: Option<PathBuf>,
}

pub struct QemuInstance {
    guest_connection: UnixStream,
    monitor_connection: UnixStream,
    shmem: Shmem,
    command: Vec<String>,
    qemu_process: Child,
    output_reader: BufReader<File>,
}

impl QemuInstance {
    pub fn from_command_json(
        path: PathBuf,
        shm_size: usize,
        base_port: u16,
        instance_id: usize,
    ) -> Result<Self> {
        let port = base_port + instance_id as u16;
        let guest_connection_path = format!("/tmp/aflControl-{}", port);
        let monitor_connection_path = format!("/tmp/monitor-{}", port);
        let qemu_out_path = format!("/tmp/qemu-out-{}", port);

        // Clean up any existing socket files
        if Path::new(&guest_connection_path).exists() {
            fs::remove_file(&guest_connection_path)?;
        }
        if Path::new(&monitor_connection_path).exists() {
            fs::remove_file(&monitor_connection_path)?;
        }

        let mut commands: Vec<String> = serde_json::from_reader(BufReader::new(File::open(path)?))?;

        // Find the index of the "-drive" argument
        let drive_index = commands
            .iter()
            .position(|cmd| cmd == "-drive")
            .ok_or_else(|| anyhow!("Could not find '-drive' argument in JSON commands"))?;

        // Extract the original disk image path from the next argument
        let drive_arg = &commands[drive_index + 1];

        let original_disk_image = {
            let start = drive_arg.find("file=").unwrap() + 5;
            let end = drive_arg[start..]
                .find(',')
                .map(|i| i + start)
                .unwrap_or_else(|| drive_arg.len());
            drive_arg[start..end].to_string()
        };

        // Create a copy of the disk image for this instance
        let instance_disk_image = format!("/tmp/root_instance_{}.qcow2", instance_id);
        let cpy_status = Command::new("qemu-img")
            .args(vec![
                "create",
                "-f",
                "qcow2",
                &instance_disk_image,
                "-b",
                &original_disk_image,
                "-F",
                "qcow2",
            ])
            .status()?;
        println!(
            "Copied disk image to <status {}>: {}",
            cpy_status, instance_disk_image
        );

        // Update the command to use the instance-specific disk image
        for command in &mut commands {
            if command.contains(&original_disk_image) {
                *command = command.replace(&original_disk_image, &instance_disk_image);
            }
        }

        let shm = QemuInstance::get_shm(shm_size, &mut commands)?;

        let qemu_append = format!("-device virtio-serial -chardev socket,path=/tmp/aflControl-{},server=on,wait=off,id=aflControl -device virtserialport,chardev=aflControl,name=aflControl", port);
        let qemu_append = qemu_append.split(' ').map(|s| s.to_owned());
        commands.extend(qemu_append);

        let qemu_append = format!(
            "-monitor unix:{},server=on,wait=off",
            monitor_connection_path
        );
        let qemu_append = qemu_append.split(' ').map(|s| s.to_owned());
        commands.extend(qemu_append);

        // Launch Qemu
        let cmd = &commands[0];
        let args = &commands[1..];

        let mut cmd = Command::new(cmd);

        let file = File::create(&qemu_out_path).unwrap();
        let stdio = Stdio::from(file);

        cmd.args(args).stderr(stdio);

        debug!("{:?}", cmd);

        let qemu_process = cmd.spawn()?;
        println!("Spawned sub-process!");

        // Increased sleep time to ensure QEMU instance is ready
        std::thread::sleep(Duration::from_secs(10));

        if Path::new(&monitor_connection_path).exists() {
            println!("Monitor socket path exists, attempting to connect...");
        } else {
            println!(
                "Monitor socket path does not exist: {}",
                monitor_connection_path
            );
            return Err(anyhow!("Monitor socket path does not exist"));
        }

        let mut monitor_connection = UnixStream::connect(&monitor_connection_path)?;
        let _s = qemu_read(&mut monitor_connection);
        println!("Connected to monitor!");

        let guest_connection = UnixStream::connect(&guest_connection_path)?;
        println!("Connected to guest pipe!");

        let file = File::open(&qemu_out_path).unwrap();
        let output_reader = BufReader::new(file);
        println!("Opened output reader!");

        Ok(Self {
            guest_connection,
            monitor_connection,
            shmem: shm,
            command: commands,
            qemu_process,
            output_reader,
        })
    }

    fn get_shm(size: usize, commands: &mut Vec<String>) -> Result<Shmem> {
        let shm: Shmem = ShmemConf::new().size(size).create()?;
        let shm_id = shm.get_os_id();
        debug!("shm ID is {}", shm.get_os_id());

        // Should see the shm file created
        let mut paths = fs::read_dir("/dev/shm")?;

        assert!(paths.any(|maybe_path| maybe_path.is_ok_and(|path| path
            .path()
            .ends_with(shm_id.strip_prefix('/').unwrap_or(shm_id)))));

        let qemu_append = format!(
            "-device ivshmem-plain,memdev=hostmem,master=on -object memory-backend-file,size={},share=on,mem-path=/dev/shm{},id=hostmem",
            size,
            shm.get_os_id());
        let qemu_append = qemu_append.split(' ').map(|s| s.to_owned());

        commands.extend(qemu_append);

        Ok(shm)
    }

    fn reconnect_monitor(&mut self) -> Result<()> {
        let monitor_connection_addrs = self.monitor_connection.peer_addr()?;
        let monitor_connection_path = monitor_connection_addrs
            .as_pathname()
            .ok_or(anyhow!("monitor connection path cleanup error"))?;
        self.monitor_connection = UnixStream::connect(monitor_connection_path)?;
        Ok(())
    }

    fn drop_inner(&mut self) -> Result<()> {
        println!("Killing Qemu instance...");
        self.qemu_process.kill()?;
        self.qemu_process.wait()?;

        let guest_connection_addrs = self.guest_connection.peer_addr()?;
        let guest_connection_path = guest_connection_addrs
            .as_pathname()
            .ok_or(anyhow!("Guest connection path cleanup error"))?;
        fs::remove_file(guest_connection_path)?;

        let monitor_connection_addrs = self.monitor_connection.peer_addr()?;
        let monitor_connection_path = monitor_connection_addrs
            .as_pathname()
            .ok_or(anyhow!("monitor connection path cleanup error"))?;
        fs::remove_file(monitor_connection_path)?;
        Ok(())
    }
}

impl Drop for QemuInstance {
    /// Clean up Qemu process and guest connection pipe
    fn drop(&mut self) {
        match self.drop_inner() {
            Ok(_) => (),
            Err(e) => error!("Qemu cleanup error: {}", e),
        }
    }
}

/// Returns None if timeout occured
fn recv_timeout(stream: &mut UnixStream, timeout: Duration) -> std::io::Result<Option<Vec<u8>>> {
    let old_timeout = stream.read_timeout()?;
    stream.set_read_timeout(Some(timeout))?;
    let mut ret = recv(stream);
    stream.set_read_timeout(old_timeout)?;

    match &mut ret {
        Err(e) => match e.kind() {
            // This OS error indicates the read timed out
            std::io::ErrorKind::WouldBlock => Ok(None),
            _ => ret.map(Some),
        },
        _ => ret.map(Some),
    }
}

fn recv<R: Read>(stream: &mut R) -> std::io::Result<Vec<u8>> {
    // @TODO zero copy?

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

fn send<W: Write>(stream: &mut W, msg: &[u8]) -> std::io::Result<()> {
    // @TODO probably faster as a single write
    stream.write_all(&u32::to_le_bytes(msg.len() as u32)[..])?;
    stream.write_all(msg)?;
    stream.flush()?;
    Ok(())
}

pub struct QemuSnapshotExecutor<S, OT>
where
    OT: ObserversTuple<S>,
    S: UsesInput,
{
    // instance: StdQemuSystem,
    // #[cfg(feature = "introspection")]
    // stats: QemuExecutorStats,
    timeout: Duration,
    name: String,
    observers: OT,
    phantom: PhantomData<S>,

    qemu_instance: QemuInstance,
    snapshot_tag: String,
}

impl<OT, S> HasObservers for QemuSnapshotExecutor<S, OT>
where
    OT: ObserversTuple<S>,
    OT: ObserversTuple<S>,
    S: UsesInput + State,
{
    fn observers(&self) -> &OT {
        &self.observers
    }

    fn observers_mut(&mut self) -> &mut OT {
        &mut self.observers
    }
}

impl<OT, S> UsesObservers for QemuSnapshotExecutor<S, OT>
where
    OT: ObserversTuple<S>,
    S: UsesInput + State,
{
    type Observers = OT;
}

impl<OT, S> UsesState for QemuSnapshotExecutor<S, OT>
where
    OT: ObserversTuple<S>,
    S: UsesInput + libafl::state::State,
{
    type State = S;
}

impl<EM, S, Z, OT> Executor<EM, Z> for QemuSnapshotExecutor<S, OT>
where
    OT: ObserversTuple<S>,
    Z: UsesState<State = S>,
    EM: EventFirer + UsesState<State = S>,
    S: Debug + UsesInput + State + HasExecutions,
    S::Input: HasTargetBytes,
{
    fn run_target(
        &mut self,
        _fuzzer: &mut Z,
        state: &mut S,
        _mgr: &mut EM,
        input: &<S as UsesInput>::Input,
    ) -> Result<ExitKind, Error> {
        // @TODO error handling

        // Send input to guest
        send(
            &mut self.qemu_instance.guest_connection,
            input.target_bytes().as_slice(),
        )
        .expect("should send sucessfully");

        // Receive signal to reset
        let r = recv_timeout(&mut self.qemu_instance.guest_connection, self.timeout)
            .expect("should recv sucessfully");

        *state.executions_mut() += 1;

        let mut exit = match r {
            Some(msg) => {
                let s = std::str::from_utf8(&msg[..])?;
                // @TODO should string match on a longer token to avoid
                // false positives; also KFENCE

                match (s.rfind("KASAN"), s.rfind("KFENCE")) {
                    (Some(_), _) => {
                        // self.qemu_instance.reconnect_monitor().expect("should recon");
                        println!("CRASH DETECTED");
                        ExitKind::Crash
                    }
                    (_ , Some(_)) => {
                        // self.qemu_instance.reconnect_monitor().expect("should recon");
                        println!("CRASH DETECTED");
                        ExitKind::Crash
                    }
                    (None, None) => ExitKind::Ok,
                }
            }
            None => ExitKind::Timeout,
        };

        let mut buf = String::new();
        loop {
            match self.qemu_instance.output_reader.read_line(&mut buf) {
                Ok(0) => break, // EOF
                Ok(_) => {
                    debug!("<qemu (guest) output> {}", buf);
                    if buf.rfind("KASAN").is_some() {
                        println!("CRASH DETECTED");
                        exit = ExitKind::Crash;
                        break;
                    }
                    buf.clear();
                }
                Err(_) => (),
            }
        }

        // @TODO need to do post-exec b/c snapshot restore clears coverage
        self.observers.post_exec_all(state, input, &exit)?;

        // Restore snapshot, resume loop
        debug!("<HOST> restore snapshot");
        let r = qemu_loadvm(
            &mut self.qemu_instance.monitor_connection,
            &self.snapshot_tag,
        )
        .expect("should loadvm sucessfully");
        debug!("{}", r);
        println!("returngin {:?}", exit);

        Ok(exit)
    }
}

impl<OT, S> Named for QemuSnapshotExecutor<S, OT>
where
    OT: ObserversTuple<S>,
    S: UsesInput,
{
    fn name(&self) -> &str {
        &self.name
    }
}

impl<OT, S> QemuSnapshotExecutor<S, OT>
where
    OT: ObserversTuple<S>,
    S: UsesInput,
{
    pub fn new(
        mut q: QemuInstance,
        snapshot_tag: String,
        observer: OT,
        name: &str,
        timeout: Duration,
    ) -> Result<Self> {
        // Receive signal to snapshot
        println!("Waiting for signal to snapshot from guest...");
        let r = recv(&mut q.guest_connection)?;
        debug!("{}", std::str::from_utf8(&r[..])?);
        let r = qemu_savevm(&mut q.monitor_connection, &snapshot_tag);
        debug!("{}", r.unwrap());

        Ok(Self {
            timeout,
            // instance: system,
            name: name.into(),
            observers: observer,
            phantom: Default::default(),

            qemu_instance: q,

            snapshot_tag,
        })
    }
}

fn trace_only(args: &Args) -> Result<()> {
    let qemu_instance = QemuInstance::from_command_json(
        args.qemu_command_json_file.clone(),
        SHM_SIZE,
        args.base_port,
        9999,
    )
    .expect("Failed to create QemuInstance");

    let shmem = ShmemConf::new()
        .os_id(qemu_instance.shmem.get_os_id())
        .open()
        .expect("Should be able to open SHM");

    let ko = KcovMapObserver::from_ptr(qemu_instance.shmem.as_ptr() as *mut u64, "kcov", None)
        .track_novelties();

    // LibAFL boilerplate
    let map_feedback = MaxMapFeedback::new(&ko);
    let mut corpus_feedback = feedback_and_fast!(
        feedback_not!(CrashFeedback::new()),
        feedback_not!(TimeoutFeedback::new()),
        map_feedback
    );

    let initial_corpus = InMemoryCorpus::<BytesInput>::new();

    let mut objective = CrashFeedback::new();

    let mut sample_state = StdState::new(
        StdRand::with_seed(0),
        initial_corpus,
        InMemoryCorpus::new(),
        &mut corpus_feedback,
        &mut objective,
    )
    .unwrap();

    let mut executor: QemuSnapshotExecutor<InMemoryCorpus<BytesInput>, _> =
        QemuSnapshotExecutor::new(
            qemu_instance,
            args.snapshot_tag.clone(),
            tuple_list!(ko.clone()),
            "HT-KF",
            Duration::from_secs(5),
        )
        .expect("Failed to create QemuSnapshotExecutor");
    // End LibAFL boilerplate

    for path in &args.initial_corpus {
        for entry in WalkDir::new(path)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|f| f.file_type().is_file())
        {
            let sample_input = BytesInput::from(fs::read(entry.path())?);

            let sym = args.symbols.clone();
            let reader = if let Some(sym) = &sym {
                DynamicKcov::new_with_symbols(&shmem, sym)
            } else {
                DynamicKcov::new(&shmem)
            };

            executor
                .observers
                .pre_exec_all(&mut sample_state, &sample_input)?;

            // Send input to guest
            send(
                &mut executor.qemu_instance.guest_connection,
                sample_input.target_bytes().as_slice(),
            )
            .expect("should send sucessfully");

            // Receive signal to reset
            let _r = recv_timeout(
                &mut executor.qemu_instance.guest_connection,
                executor.timeout,
            )
            .expect("should recv sucessfully");

            let mut path = args.output_dir.clone();
            path.push(entry.path().file_name().unwrap());
            let file = File::create(path)?;
            let mut writer = BufWriter::new(file);

            if sym.is_some() {
                //@TODO error handling
                let t = reader.get_trace().expect("should parse");
                for l in t {
                    println!("{}:{}:{}", l.file, l.function_name, l.line);
                    writeln!(writer, "{}:{}:{}", l.file, l.function_name, l.line)?;
                }
            } else {
                let slice =
                    unsafe { std::slice::from_raw_parts(shmem.as_ptr() as *mut u64, SHM_SIZE / 8) };

                let mut has_frame_errors = true;
                let mut starting_frame_level = 0;
                while has_frame_errors {
                    has_frame_errors = false;
                    let mut in_frame = starting_frame_level;
                    println!("Starting trace parse");

                    for i in 0..SHM_SIZE / 8 {
                        let ii = SHM_SIZE / 8 - 1 - i;
                        let e = slice[ii];

                        if e == 0xdeadbeef {
                            in_frame += 1;
                            println!("0x{:x} [{}]", e, in_frame);
                        } else if e == 0xbeefdead {
                            in_frame -= 1;
                            println!("0x{:x} [{}]", e, in_frame);
                            if in_frame < 0 {
                                has_frame_errors = true;
                                starting_frame_level += 1;
                                break;
                            }
                        } else if in_frame > 0 && e != 0 {
                            // TODO should not write in case there is a frame error
                            writeln!(writer, "0x{:x}", e)?;
                            if ii % 1000 == 0 {
                                println!("{}: 0x{:x}\n...", ii, e);
                            }
                        }
                    }
                }
            }
            println!("DONE TRACING");

            executor
                .observers
                .post_exec_all(&mut sample_state, &sample_input, &ExitKind::Ok)?;

            // Restore snapshot, resume loop
            let _r = qemu_loadvm(
                &mut executor.qemu_instance.monitor_connection,
                &executor.snapshot_tag,
            )
            .expect("should loadvm sucessfully");
        }
    }

    Ok(())
}

fn main() -> Result<()> {
    let args = Args::parse();
    println!(
        "Attempting to open JSON file at path: {:?}",
        args.qemu_command_json_file
    );

    let _ = fs::create_dir(&args.output_dir);
    let _ = fs::create_dir(&args.queue_dir);

    let shmem_provider = StdShMemProvider::new().expect("Failed to init shared memory");

    if args.trace_only {
        return trace_only(&args);
    }

    let monitor = MultiMonitor::new(|s| println!("{s}"));

    let run_client = |_state: Option<_>,
                      mut restarting_mgr,
                      core_id: libafl_bolts::core_affinity::CoreId| {
        let instance_id = core_id.0; // Use core_id as instance_id
        let qemu_instance = QemuInstance::from_command_json(
            args.qemu_command_json_file.clone(),
            SHM_SIZE,
            args.base_port,
            instance_id,
        )
        .expect("Failed to create QemuInstance");

        let ko = KcovMapObserver::from_ptr(qemu_instance.shmem.as_ptr() as *mut u64, "kcov", None)
            .track_novelties();

        let map_feedback = MaxMapFeedback::new(&ko);
        let mut corpus_feedback = feedback_and_fast!(
            feedback_not!(CrashFeedback::new()),
            feedback_not!(TimeoutFeedback::new()),
            map_feedback
        );

        let mut objective = CrashFeedback::new();

        let mut core_queue_dir = args.queue_dir.clone();
        core_queue_dir.push(format!("{}", instance_id));
        fs::create_dir(&core_queue_dir).expect("Per core queue dir creation failed");

        let initial_corpus = CachedOnDiskCorpus::<BytesInput>::new(&core_queue_dir, 100)?;
        let output_corpus = OnDiskCorpus::<BytesInput>::new(&args.output_dir)?;

        // println!("initial {:?}", initial_corpus.dir_path());
        println!("out {:?}", output_corpus.dir_path());

        let mut sample_state = StdState::new(
            StdRand::with_seed(0),
            initial_corpus,
            output_corpus,
            &mut corpus_feedback,
            &mut objective,
        )
        .unwrap();

        let _shmem = ShmemConf::new()
            .os_id(qemu_instance.shmem.get_os_id())
            .open()
            .expect("Should be able to open SHM");

        let mut executor = QemuSnapshotExecutor::new(
            qemu_instance,
            args.snapshot_tag.clone(),
            tuple_list!(ko.clone()),
            "HT-KF",
            Duration::from_secs(5),
        )
        .expect("Failed to create QemuSnapshotExecutor");

        let mut fuzzer: StdFuzzer<_, _, _, _> =
            StdFuzzer::new(RandScheduler::new(), corpus_feedback, objective);

        sample_state.load_initial_inputs_by_filenames(
            &mut fuzzer,
            &mut executor,
            &mut restarting_mgr,
            &args.initial_corpus[..],
        )?;

        if args.use_grimoire {
            println!("Using Grimoire mutators");
            // Grimoire
            let generalization = GeneralizationStage::new(&ko);

            // Setup a mutational stage with a basic bytes mutator
            let mutator = StdScheduledMutator::with_max_stack_pow(havoc_mutations(), 2);
            let grimoire_mutator = StdScheduledMutator::with_max_stack_pow(
                tuple_list!(
                    GrimoireExtensionMutator::new(),
                    GrimoireRecursiveReplacementMutator::new(),
                    GrimoireStringReplacementMutator::new(),
                    // give more probability to avoid large inputs
                    GrimoireRandomDeleteMutator::new(),
                    GrimoireRandomDeleteMutator::new(),
                ),
                3,
            );
            let mut stages = tuple_list!(
                generalization,
                StdMutationalStage::new(mutator),
                StdMutationalStage::transforming(grimoire_mutator)
            );
            fuzzer
                .fuzz_loop_for(
                    &mut stages,
                    &mut executor,
                    &mut sample_state,
                    &mut restarting_mgr,
                    10000,
                )
                .expect("Error in the fuzzing loop");
        } else {
            println!("Using basic mutators");
            // Basic
            let mutator = StdScheduledMutator::new(havoc_mutations());

            let mut stages = tuple_list!(StdMutationalStage::new(mutator));

            fuzzer
                .fuzz_loop_for(
                    &mut stages,
                    &mut executor,
                    &mut sample_state,
                    &mut restarting_mgr,
                    10000,
                )
                .expect("Error in the fuzzing loop");
        }

        if instance_id == 0 {
            let mut processed_files: HashSet<PathBuf> = HashSet::new();

            if let Some(monitor_dir) = args.monitor_dir.clone() {
                println!(
                    "Instance {} is monitoring directory: {:?}",
                    instance_id, monitor_dir
                );
                let corpus = Arc::new(Mutex::new(sample_state.corpus().clone()));
                loop {
                    if let Ok(entries) = fs::read_dir(monitor_dir.as_path()) {
                        for entry in entries.flatten() {
                            if let Ok(metadata) = entry.metadata() {
                                if metadata.is_file() {
                                    let entry_path = entry.path();
                                    if !processed_files.contains(&entry_path) {
                                        if let Ok(buffer) = fs::read(&entry_path) {
                                            let input = BytesInput::new(buffer);
                                            if let Err(e) = corpus.lock().unwrap().add(input.into())
                                            {
                                                println!(
                                                    "Failed to add new test case from {:?}: {:?}",
                                                    entry_path, e
                                                );
                                            } else {
                                                println!(
                                                    "Added new test case from {:?}",
                                                    entry_path
                                                );
                                                processed_files.insert(entry_path);
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    thread::sleep(Duration::from_secs(10));
                }
            }
        }

        // Cleanup disk image for the instance
        let instance_disk_image = format!("/tmp/root_instance_{}.qcow2", instance_id);
        if Path::new(&instance_disk_image).exists() {
            fs::remove_file(&instance_disk_image).expect("Failed to remove instance disk image");
        }

        Ok(())
    };

    let cores_str = format!("0-{}", args.num_instances - 1); // Specify the cores to bind to
    let cores = Cores::from_cmdline(&cores_str).expect("Failed to parse cores");

    match Launcher::builder()
        .shmem_provider(shmem_provider)
        .configuration(EventConfig::from_name("default"))
        .monitor(monitor)
        .run_client(&run_client)
        .cores(&cores)
        .broker_port(1337)
        .build()
        .launch()
    {
        Ok(()) => Ok(()),
        Err(Error::ShuttingDown) => {
            println!("Fuzzing stopped by user. Good bye.");
            Ok(())
        }
        Err(err) => panic!("Failed to run launcher: {:?}", err),
    }
}

/// Read the response from the QEMU monitor
fn qemu_read(reader: &mut UnixStream) -> Result<String> {
    // @TODO add timeout
    let mut buffer = [0; 512];
    let mut response = Vec::new();
    loop {
        let bytes_read = reader.read(&mut buffer)?;
        if bytes_read == 0 {
            break; // End of stream
        }
        response.extend_from_slice(&buffer[..bytes_read]);

        // Check if we have received the QEMU prompt indicating the end of the response
        if response.ends_with(b"(qemu) ") {
            break;
        }
    }

    // Convert the response to a string
    Ok(std::str::from_utf8(&response)?.to_owned())
}

/// Send command to the interactive QEMU monitor
fn qemu_savevm(stream: &mut UnixStream, tag: &str) -> Result<String> {
    stream.write_all(format!("savevm {}\n", tag).as_bytes())?;
    qemu_read(stream)
}

fn qemu_loadvm(stream: &mut UnixStream, tag: &str) -> Result<String> {
    stream.write_all(format!("loadvm {}\n", tag).as_bytes())?;
    qemu_read(stream)
}
