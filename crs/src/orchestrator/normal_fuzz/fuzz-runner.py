import sys
import json
import subprocess as sp
import os
from os.path import join
import time

mdfile = sys.argv[1]
f = open(mdfile)
md = json.loads(f.read())
f.close()


cwd = os.getcwd()
cp_path = md["cp_path"]
image_id = md["image_id"].strip()
harness_dir = os.path.dirname(join(cp_path, md["harnesses"][0]["source"]))

binary_path = join(md["binary_path"])

build_cmd = md["build_script"]
## @TODO I think the official images / VMs have environment variables for each volume
initial_corpus_dir = "/out/seeds"
fuzz_out_dir = "/out/afl-out"
env_args = f"-v {join(cp_path,'work')}:/work -v {join(cp_path,'src')}:/src -v {md['output_dir_abspath']}/out:/out"

timestamp = int(time.time())

sp.run(f"cd {cp_path} ; cp .env.ins.docker .env.ins.docker.{timestamp}", shell=True)

with open(join(cp_path, f".env.ins.docker.{timestamp}"), "a") as f:
    f.write("\nCC=/opt/AFLplusplus/afl-gcc\n")
    f.write("\nCXX=/opt/AFLplusplus/afl-g++\n")

# Build
print(
    f"cd {cp_path}; DOCKER_VOL_ARGS='{env_args}' DOCKER_IMAGE_NAME={image_id} DOCKER_RUN_ENV_FILE=.env.ins.docker.{timestamp} {build_cmd}"
)
sp.run(
    f"cd {cp_path}; DOCKER_VOL_ARGS='{env_args}' DOCKER_IMAGE_NAME={image_id} DOCKER_RUN_ENV_FILE=.env.ins.docker.{timestamp} {build_cmd}",
    shell=True,
)


# Copy over seeds
os.makedirs(f"{md['output_dir_abspath']}/out/seeds", exist_ok=True)

for ao in md.get("analysis_output",[]):
    for inputs in ao["benign_inputs"]:
        if inputs["format"] == "raw":
            print(inputs)
            sp.run(
                f"cp -r {cp_path}/{inputs['dir']}/. -t {md['output_dir_abspath']}/{initial_corpus_dir}",
                shell=True,
            )

corpus_dir = f"{md['output_dir_abspath']}/{initial_corpus_dir}"

print(f"Checking {corpus_dir}")
if os.listdir(corpus_dir) == []:
    with open(join(corpus_dir, "hi.txt"), "w") as f:
        f.write("HI!")

# Run fuzzer
## We are restarting the VM after every 45m to avoid it getting into a bad state
## In particular, KCOV seems to stop working after roughly this amount of time,
## causing no new coverage to be reported

# TODO: figure out whether this needs to be empty or @@ for stdin
input_method = ""

fuzz_command = f"timeout -k 1m 4h /opt/AFLplusplus/afl-fuzz -i {initial_corpus_dir} -o {fuzz_out_dir} -t 10000+ -- /{binary_path} {input_method}"
print(fuzz_command)


## Note that we have hard-coded the virtme command rather than attempting to use
## the official AIxCC scripts. This is because these scripts are in flux, so it's
## not clear what the official API for running custom commands in the VM will be.
docker_command = f"""DOCKER_VOL_ARGS='{env_args}' DOCKER_IMAGE_NAME={image_id} ./run.sh custom {fuzz_command} """
print(f"cd {cp_path}; {docker_command}")
sp.run(f"cd {cp_path}; {docker_command}", shell=True)
