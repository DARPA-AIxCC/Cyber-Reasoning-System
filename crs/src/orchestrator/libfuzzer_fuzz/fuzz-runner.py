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
initial_corpus_dir = "/out/afl-out/queue"
host_additional_seeds = (
    join(os.getenv("AIXCC_CRS_SCRATCH_SPACE"), "peach", md["subject"], md["bug_id"], "")
    if os.getenv("AIXCC_CRS_SCRATCH_SPACE", None)
    else ""
)
container_additional_seeds = "/extra_seeds"

os.makedirs(host_additional_seeds, exist_ok=True)

fuzz_out_dir = "/out/afl-out"
env_args = f"-v {join(cp_path,'work')}:/work -v {join(cp_path,'src')}:/src -v {host_additional_seeds}:{container_additional_seeds} -v {md['output_dir_abspath']}/out:/out"

timestamp = int(time.time())

sp.run(f"cd {cp_path} ; cp .env.ins.docker .env.ins.docker.{timestamp}", shell=True)

print(f"making {md['output_dir_abspath']}/{fuzz_out_dir}/crashes")
os.makedirs(f"{md['output_dir_abspath']}/{fuzz_out_dir}/crashes", exist_ok=True)

with open(join(cp_path, f".env.ins.docker.{timestamp}"), "a") as f:
    f.write(f"\nartifact_prefix='{fuzz_out_dir}/crashes'\n")

# Build
print(
    f"cd {cp_path}; DOCKER_VOL_ARGS='{env_args}' DOCKER_RUN_ENV_FILE=.env.ins.docker.{timestamp} {build_cmd}"
)
sp.run(
    f"cd {cp_path}; DOCKER_VOL_ARGS='{env_args}' DOCKER_RUN_ENV_FILE=.env.ins.docker.{timestamp} {build_cmd}",
    shell=True,
)


# Copy over seeds
os.makedirs(f"{md['output_dir_abspath']}/out/afl-out/queue", exist_ok=True)

for ao in md.get("analysis_output", []):
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


# Run A seed through run_pov
sp.run(
    f"cd {cp_path}; DOCKER_VOL_ARGS='{env_args}' ./run.sh run_pov {join(corpus_dir,os.listdir(corpus_dir)[0])} {md['harnesses'][0]['name']} ",
    shell=True,
)

print(
    f'strings {join(cp_path,md["binary_path"])} | sort | uniq | xargs -0 -d "\n" -I {{}} echo =\\"{{}}\\" | nl -s "" | sed "s/^\s*//g" > {join(cp_path,"work","autodict.dict")}'
)

strings = sp.run(
    f'strings {join(cp_path,md["binary_path"])} | sort | uniq | xargs -0 -d "\n" -I {{}} echo =\\"{{}}\\" | nl -s "" | sed "s/^\s*//g" > {join(cp_path,"work","autodict.dict")}',
    shell=True,
)


dict_str = " "
if strings.returncode != 0:
    dict_str = "-dict=/work/autodict.dict"

# Run 10 fuzzer instances with agressive length expansion, do not stop on crashes, give 1 sec execution and 2048 byte length
fuzz_command = f"bash -c 'cd /out/ && timeout -k 1m 4h /{binary_path} -fork={  os.getenv('CPU_COUNT',5) } -len_control=20 -use_value_profile=1 {dict_str} -ignore_crashes=1 -detect_leaks=0 -artifact_prefix={fuzz_out_dir}/crashes/ -max_len=2000000 -timeout=5 {initial_corpus_dir} {container_additional_seeds}'"
non_dict_fuzz_command = f"bash -c 'cd /out/ && timeout -k 1m 4h /{binary_path} -fork={  os.getenv('CPU_COUNT',5) } -len_control=20 -use_value_profile=1 -ignore_crashes=1 -detect_leaks=0 -artifact_prefix={fuzz_out_dir}/crashes/ -max_len=2000000 -timeout=5 {initial_corpus_dir} {container_additional_seeds}'"

print(fuzz_command)


## Note that we have hard-coded the virtme command rather than attempting to use
## the official AIxCC scripts. This is because these scripts are in flux, so it's
## not clear what the official API for running custom commands in the VM will be.

docker_command = f"""DOCKER_VOL_ARGS='{env_args}' ./run.sh custom {fuzz_command} """
non_dict_docker_command = (
    f"""DOCKER_VOL_ARGS='{env_args}' ./run.sh custom {non_dict_fuzz_command} """
)


def fuzz_exec(cp_path, docker_command):
    print(f"cd {cp_path}; {docker_command}")
    env = os.environ.copy()
    old_path = env["PATH"]

    env["TOOL_NAME"] = "libfuzzer_fuzz"
    env["PATH"] = f"/app/orchestrator/fake-docker/:{old_path}"

    r = sp.run(f"cd {cp_path}; {docker_command}", shell=True, env=env)

    if r.returncode != 0:
        env["PATH"] = old_path
        r = sp.run(f"cd {cp_path}; {docker_command}", shell=True, env=env)
    return r


r = fuzz_exec(cp_path, docker_command)

if r.returncode != 0:
    fuzz_exec(cp_path, non_dict_docker_command)
