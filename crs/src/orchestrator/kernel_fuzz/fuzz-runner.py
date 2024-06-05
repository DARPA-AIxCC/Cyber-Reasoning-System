import sys
import json
import subprocess as sp
import os
from os.path import join

mdfile = sys.argv[1]
f = open(mdfile)
md = json.loads(f.read())
f.close()


cwd = os.getcwd()
cp_path = md["cp_path"]
cp_src = md["cp_src"]
image_id = md["image_id"]
harness_dir = os.path.dirname(join(cp_path,md["harnesses"][0]["source"]))
harness_binary_path = join(cp_path,md["harnesses"][0]["binary"])
kernel_binary_path = join(cp_path,md["binary_path"])
kernel_bz_image = join(cp_src,"arch","x86","boot","bzImage")
build_cmd = md["build_script"]
## @TODO I think the official images / VMs have environment variables for each volume
initial_corpus_dir = "out/seeds"
fuzz_out_dir = "out/afl-out"
env_args=f"-v {join(cp_path,'work')}:/work -v {join(cp_path,'src')}:/src -v {md['output_dir_abspath']}/out:/out"

# Apply Patches To Kernel for instrumentation
print(f"cd {cp_path}; DOCKER_VOL_ARGS='{env_args}' bash instrument.sh")
sp.run(f"cd {cp_path}; DOCKER_VOL_ARGS='{env_args}' bash instrument.sh", shell=True)

# Copy special harness version
print(f"bash -c 'cp kcov-setup/harness-patches/* -t {harness_dir}'")
sp.run(f"bash -c 'cp kcov-setup/harness-patches/* -t {harness_dir}'", shell=True)

# Build
sp.run(f"cd {cp_path}; DOCKER_VOL_ARGS='{env_args}' {build_cmd}", shell=True)

# Copy over seeds
os.makedirs(f"{cp_path}/out/seeds", exist_ok=True)

for ao in md.get("analysis_output",[]):
    for inputs in ao["benign_inputs"]:
        if inputs["format"] == "raw":
            print(inputs)
            sp.run(f"cp -r {inputs['dir']} -t {cp_path}/{initial_corpus_dir}", shell=True)

# Instrument
sp.run(f"./e9afl/e9afl {harness_binary_path}", shell=True)
sp.run(f"cp {os.path.basename(harness_binary_path)}.afl {os.path.dirname(harness_binary_path)}", shell=True)

# Run fuzzer
## We are restarting the VM after every 45m to avoid it getting into a bad state
## In particular, KCOV seems to stop working after roughly this amount of time, 
## causing no new coverage to be reported

fuzz_command = f"'AFL_AUTORESUME=1 AFL_NO_STARTUP_CALIBRATION=1 timeout -k 1m 5m afl-fuzz -i {initial_corpus_dir} -o {fuzz_out_dir} -t 20000+ -- {md["harnesses"][0]["binary"]}.afl @@'"
print(fuzz_command)

with open(join(cp_path,"out","fuzz-cmd.sh"),"w") as f:
    f.write(fuzz_command)
sp.run(f"cd {cp_path}; chmod +x out/fuzz-cmd.sh", shell=True)
    

## Note that we have hard-coded the virtme command rather than attempting to use
## the official AIxCC scripts. This is because these scripts are in flux, so it's 
## not clear what the official API for running custom commands in the VM will be. 
vm_command = f"virtme-run --verbose --show-boot-console --kimg  {kernel_bz_image} --memory 2G --mods=auto --rwdir=/out --disable-microvm --script-sh /out/fuzz-cmd.sh"
print(vm_command)
docker_command = f"""docker run -it {env_args} {image_id} sh -c "while true; do echo restarting vm...; {vm_command}; sleep 1; done" """
print(f"cd {cp_path}; {docker_command}")
sp.run(f"cd {cp_path}; {docker_command}", shell=True)
