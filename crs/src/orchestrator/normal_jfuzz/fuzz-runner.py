import shutil
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
harness_java = join(cp_path, md["harnesses"][0]["source"])
harness_dir = os.path.dirname(harness_java)
harness_class_dir = os.path.dirname(join(cp_path, md["harnesses"][0]["binary"]))

host_additional_seeds = (
    join(os.getenv("AIXCC_CRS_SCRATCH_SPACE"), "peach", md["subject"], md["bug_id"], "")
    if os.getenv("AIXCC_CRS_SCRATCH_SPACE", None)
    else ""
)
container_additional_seeds = "/extra_seeds"

magic_string = "src/main/java/"
harness_class_name = harness_java[
    harness_java.index(magic_string) + len(magic_string) :
].replace("/", ".")[: -len(".java")]


build_cmd = md["build_script"]
## @TODO I think the official images / VMs have environment variables for each volume
initial_corpus_dir = "/out/queue"
reproducers_out_dir = "/out/reproducers"
artifacts_out_dir = "/out/crashes"

sp.run(f"mkdir -p {md['output_dir_abspath']}{artifacts_out_dir}", shell=True)
sp.run(f"mkdir -p {md['output_dir_abspath']}{reproducers_out_dir}", shell=True)
sp.run(f"mkdir -p {md['output_dir_abspath']}{initial_corpus_dir}", shell=True)


env_args = f"-v {join(cp_path,'work')}:/work -v {join(cp_path,'src')}:/src -v {host_additional_seeds}:{container_additional_seeds} -v {md['output_dir_abspath']}/out:/out"

timestamp = int(time.time())

sp.run(
    f"cd {cp_path} ; cp .env.docker .env.ins.docker.{timestamp} ",
    shell=True,
)

# with open(join(cp_path, f".env.ins.docker.{timestamp}"), "a") as f:
#     pass
#     # f.write("\nCC=/usr/local/bin/afl-gcc\n")
#     # f.write("\nCXX=/usr/local/bin/afl-g++\n")

# Build
print(
    f"cd {cp_path}; DOCKER_VOL_ARGS='{env_args}' DOCKER_RUN_ENV_FILE=.env.ins.docker.{timestamp} {build_cmd}"
)
sp.run(
    f"cd {cp_path}; DOCKER_VOL_ARGS='{env_args}' DOCKER_RUN_ENV_FILE=.env.ins.docker.{timestamp} {build_cmd}",
    shell=True,
)

# Copy over seeds
os.makedirs(f"{md['output_dir_abspath']}/out/seeds", exist_ok=True)

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


classpath_sources = [
    f"$(find /{os.path.dirname(md['harnesses'][0]['binary'])} -name '*.jar' -printf '%p:' | sed 's/:$//')"
]

dict_text = ""
if os.path.exists(join(cp_path, "dicts", "dict.txt")):
    shutil.copy(join(cp_path, "dicts", "dict.txt"), join(cp_path, "work", "dict.txt"))
    dict_text = "-dict=/work/dict.txt"

# CUSTOM_MUTATOR='/work/custom_mutator.so'
# LD_PRELOAD=/work/custom_mutator.so


fuzz_command = f"""bash -c 
    'timeout -k 1m 4h /classpath/jazzer/jazzer 
    -artifact_prefix={artifacts_out_dir}/crash_
    {dict_text} --trace=all -use_value_profile=1                
    -fork={  os.getenv("CPU_COUNT",5)  } -ignore_crashes=1 -timeout=10 -max_len=2000000 -reload=1
    --reproducer_path={reproducers_out_dir}
    --agent_path=/classpath/jazzer/jazzer_standalone_deploy.jar 
    "--cp={":".join(classpath_sources)}" 
    --target_class={harness_class_name} 
    --jvm_args="-Djdk.attach.allowAttachSelf=true:-XX\:+StartAttachListener" 
    --keep_going=20 {initial_corpus_dir} {container_additional_seeds}'""".replace(
    "\n", " "
)
    
    
with open(join(cp_path,"work","run_script.sh"),"w") as f:
    f.write(fuzz_command)

os.system(f"chmod +x {join(cp_path,'work','run_script.sh')}")

print(fuzz_command)

docker_command = f"""DOCKER_VOL_ARGS='{env_args}' ./run.sh custom bash -c '/work/run_script.sh' ; """
print(f"cd {cp_path}; {docker_command}")

env = os.environ.copy()
old_path = env["PATH"]
env["TOOL_NAME"] = "jfuzz"
env["PATH"] = f"/app/orchestrator/fake-docker/:{old_path}"

r = sp.run(f"cd {cp_path}; {docker_command}", shell=True, env=env)

if r.returncode != 0:
    env["PATH"] = old_path
    r = sp.run(f"cd {cp_path}; {docker_command}", shell=True, env=env)
