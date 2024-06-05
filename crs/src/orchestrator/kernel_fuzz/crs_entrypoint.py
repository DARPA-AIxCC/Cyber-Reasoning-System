### Entrypoint for CRS
##    Executes in CRS context; can spin up CP instances as needed

import json
from random import randint
import sys
import os
import time
import subprocess as sp
import shutil
import pathlib
from os.path import join
from base64 import b64encode

f = open(sys.argv[1])
md = json.loads(f.read())
f.close()

trace_src_dir, trace_out_dir = (
    sys.argv[2].split(":") if len(sys.argv) > 2 else (None, None)
)

cp_src = md["cp_src"]
cp_path = md["cp_path"]

os.makedirs(f"{cp_path}/out", exist_ok=True)

name = md["harnesses"][0]["name"]
bin = md["harnesses"][0]["binary"]
bin_bk = os.path.basename(bin)

create_new_disk_image = True

# TODO CLI interface
# TODO change hard-coded paths to environment variables

# Clean dir for local testing
# sp.run(f"cd {cp_path}; make cpsrc-clean", shell=True);
# sp.run(f"cd {cp_path}; make cpsrc-prepare", shell=True);
# sp.run(f"cd {cp_src}; make docker-pull", shell=True);

# Copy seed over to enable testing
if trace_out_dir:
    sp.run(f"rm -rf {cp_path}/out/corpus", shell=True)
    sp.run(f"cp -r {trace_src_dir} {cp_path}/out/corpus", shell=True)
else:
    # TODO remove later for realistic scenario
    sp.run(
        f"cp -r challenge-001-cp-files/corpus {cp_path}/out",
        shell=True,
    )


# Apply patches
def make_image(md, cp_path, create_new_disk_image):
    if create_new_disk_image:
        sp.run(f"cp -r virtme-ng {cp_path}/out/vng", shell=True)
        magic_incantation = """/out/vng/virtme-run --kimg /src/linux_kernel/arch/x86_64/boot/bzImage --memory 2G --mods=auto --blk-disk newroot=/out/root.qcow2 --script-sh "mkfs.ext4 /dev/vda && mount /dev/vda '/mnt' && rsync -v -a --one-file-system --exclude '/src' --exclude '/mnt' --exclude '/out/root.qcow2' / '/mnt'/" """
        img_create = "qemu-img create -f qcow2 /out/root.qcow2 200G"
        p = sp.run(f"cd {cp_path}; ./run.sh custom {img_create}", shell=True)
        p = sp.run(
            f"cd {cp_path}; ./run.sh custom sudo {magic_incantation}", shell=True
        )
    else:
        sp.run("zstd --decompress challenge-001-cp-files/root.qcow2.zst", shell=True)
        sp.run(
            f"mv challenge-001-cp-files/root.qcow2 {cp_path}/out",
            shell=True,
        )


kernel_cache_dir =  join(os.getenv("AIXCC_CRS_SCRATCH_SPACE"), "kernel_cache", md["subject"], md["bug_id"], "") if os.getenv("AIXCC_CRS_SCRATCH_SPACE") else None
has_cache = False

if kernel_cache_dir:
    os.makedirs(kernel_cache_dir,exist_ok=True)
    while os.path.exists(join(kernel_cache_dir,".copy_lock")):
        print("Waiting for the copy lock to be removed")
        time.sleep(10)
        
    if os.path.exists(join(kernel_cache_dir,'.kfuzz')) and not os.path.exists(f"{cp_path}/.kfuzz"):
        print("Copying cached instance")
        sp.run(f"rsync -azS {kernel_cache_dir}/. {cp_path}",shell=True)
    
if not os.path.exists(f"{cp_path}/.kfuzz"):
    print("Building")
    p = sp.run(
        f"cd {cp_src}; {os.getcwd()}/kernel-patches/apply.sh",
        shell=True,
        env=dict(os.environ, PATCHES_DIR=f"{os.getcwd()}/kernel-patches"),
    )
    if p.returncode != 0:
        print("Error applying patches!")
        exit(1)
    # Build Kernel
    p = sp.run(f"cd {cp_path}; ./run.sh build", shell=True)
    if p.returncode != 0:
        print("Error building patched kernel!")
        exit(1)

    ## CLI GRABBER
    sp.run(f"cp {cp_path}/{bin} {bin_bk} ", shell=True)
    sp.run(f"cp cli-grabber/target/release/cli-grabber {cp_path}/{bin}", shell=True)

    sp.run(
        f"echo ' HEALING TOUCH SPECIAL TOKEN {'a'*64}' > {cp_path}/special_token.blob",
        shell=True,
    )
    p = sp.run(
        f"cd {cp_path}; ./run.sh run_pov  special_token.blob {name}",
        shell=True,
        capture_output=True,
    )
    so = p.stdout.decode("utf-8")
    print(so)

    CLI_GRABBER_TOKEN = "<CLI GRABBER JSON>"
    jl = [l for l in so.splitlines() if CLI_GRABBER_TOKEN in l]
    j = json.loads(jl[0].split(CLI_GRABBER_TOKEN)[1])
    print(j)

    # restore real harness
    sp.run(f"cp {bin_bk} {cp_path}/{bin}", shell=True)

    # convert command to base64 for template
    cmd = f"""cd {j["cwd"]}; /out/guest -i {j["cmd"][j["idx"]]} -b -- {" ".join(j["cmd"])}"""

    print(cmd)
    cmd = b64encode(cmd.encode("utf-8")).decode("utf-8")
    print(cmd)
    # exit(0)

    # Copy guest binaries to `out` volume to bake into VM disk image
    # TODO copy in shared library dependencies or build inside docker image
    # TODO ensure no naming collisions with CP harness names
    sp.run(
        f"cp virtio-serial-guest/target/release/guest {cp_path}/out",
        shell=True,
    )

    # Copy fuzzer to `out` volume; only needs to be in docker, not in VM image
    # TODO copy in shared library dependencies or build inside docker image
    # TODO ensure no naming collisions with CP harness names
    sp.run(f"cp target/release/libafl-kcov {cp_path}/out", shell=True)

    # Do virtme-ng magic
    make_image(md, cp_path, create_new_disk_image)

    # Template command with kernel / disk image
    f = open("challenge-001-cp-files/template.json")
    c = f.read()
    f.close()

    bzimage_path = None
    for a in md["cp_sources"][0]["artifacts"]:
        if "bzImage" in a:
            bzimage_path = a
            if bzimage_path[0] != "/":
                bzimage_path = "/" + bzimage_path

            break
    if bzimage_path is None:
        print("Cannot locate kernel artifact")
        exit(1)

    c = c.format("/out/root.qcow2", bzimage_path, cmd)

    f = open(f"{cp_path}/out/run.json", "w")
    f.write(c)
    f.close()
    f = open(f"{cp_path}/.kfuzz", "w")
    f.write("patched")
    f.close()
    
    if kernel_cache_dir:
        print("Will cache. Sleep to prevent overwrites")
        time.sleep(1 + randint(1,10) )
        
        if not os.path.exists(join(kernel_cache_dir,'.copy_lock')):
            print("Got lock!")
            pathlib.Path(join(kernel_cache_dir,'.copy_lock')).touch()
            sp.run(f"bash -c 'rsync -azS {cp_path}/. {kernel_cache_dir} ; rm {join(kernel_cache_dir,'.copy_lock')}  '",shell=True)
            print("Copied over")


# Run fuzzer (need to add CLI to take in JSON file)
host_additional_seeds = (
    join(os.getenv("AIXCC_CRS_SCRATCH_SPACE"), "peach", md["subject"], md["bug_id"], "")
    if os.getenv("AIXCC_CRS_SCRATCH_SPACE", None)
    else ""
)
container_additional_seeds = "/extra_seeds"

env_args = f"-v {join(cp_path,'work')}:/work -v {join(cp_path,'src')}:/src -v {host_additional_seeds}:{container_additional_seeds} -v {cp_path}/out:/out/ -v {md['output_dir_abspath']}/out:/out/fuzzer-out"


sp.run(f"rm -r {cp_path}/out/fuzzer-out", shell=True)

command = f"cd {cp_path}; DOCKER_VOL_ARGS='{env_args}' ./run.sh custom bash -c 'sudo /out/libafl-kcov {'-t' if trace_src_dir else '' } --monitor-dir {container_additional_seeds} --num-instances { os.getenv('CPU_COUNT',5)  } --use-grimoire -q /out/run.json -i /out/corpus/ -o /out/fuzzer-out/crashes --queue-dir /out/fuzzer-out/queue'"

env = os.environ.copy()
old_path = env["PATH"]

env["TOOL_NAME"] = "kfuzz"
env["PATH"] = f"/app/orchestrator/fake-docker/:{old_path}"

r = sp.run(command, shell=True, env=env)

if r.returncode != 0:
    env["PATH"] = old_path
    r = sp.run(command, shell=True, env=env)

if trace_out_dir:
    shutil.rmtree(trace_out_dir, ignore_errors=True)
    shutil.move(join(md["output_dir_abspath"], "out", "crashes"), trace_out_dir)
