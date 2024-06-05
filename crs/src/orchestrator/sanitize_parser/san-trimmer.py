import re
import json
import sys
import subprocess as sp
import os
import time
from os.path import join

mdfile = sys.argv[1]
output = sys.argv[2]
f = open(mdfile)
md = json.loads(f.read())
f.close()

cwd = os.getcwd()
cp_path = md["cp_path"]
test_cmd = md["test_script"]
timestamp = int(time.time())

# Rebuild with debug flags - assume this is already done
# print(f"cd {cp_path} ; DOCKER_RUN_ENV_FILE=.env.ins.docker {md['build_script']}")
# sp.run(
#     f"cd {cp_path} ; DOCKER_RUN_ENV_FILE=.env.ins.docker {md['build_script']}",
#     shell=True,
# )

source_paths = []

for source in md.get("cp_sources", []):
    source_paths.append(source["name"])

# for harness in md.get("harnesses", []):
#    source_paths.append(harness["source"])


# Note: there should only be one POV, but just looping in case there are multiple for some reason
for ao in md.get("analysis_output", []):
    for ei in ao["exploit_inputs"]:
        if ei["format"] == "raw":
            for input_file in os.listdir(os.path.join(cp_path, ei["dir"])):
                pov_file = os.path.join(cp_path, ei["dir"], input_file)
assert pov_file is not None
# print(f"{test_cmd} {pov_file}")
p = sp.run(f"{test_cmd} {pov_file}", shell=True, capture_output=True)
o = p.stdout.decode("utf-8", errors="ignore")
e = p.stderr.decode("utf-8", errors="ignore")
outlines = o.splitlines()
errlines = e.splitlines()

# In the case of ASAN the only output we are searching for comes from stderr
outlines = outlines + errlines


def identity(x):
    return x

def parse_c_line(line: str):
    # print(f"Fixing {line}")
    m = re.match(".*#\d+ .* in (.*) (.*?:\d+)(:\d+)?.*", line)
    if not m:
        return [], []

    func = m.group(1)
    file = m.group(2)


    prefix_search =  re.match("/src/harnesses/(.+?)/",file)
    trimmed = False

    if prefix_search:
        trimmed = True
        if not prefix_search.group(1) in source_paths:
            file = file[len(prefix_search.group(0)):]
        else:
            file = file.removeprefix("/src/harnesses/")

    for source in source_paths:
        if source in file:
            ind = file.index(source)
            file = file[ind+len(source)+1:]
            break
    else:
        if not trimmed:
            return [],[]

    if func.startswith("_") or "sanitizer_common_interceptors_format" in file:
        return [], []
    return [func], [file]
    pass


def fix_paths_c(line: str):
    m = re.match("(.*#\d+ .* in) (.*) (.*?:\d+)((?::\d+)?.*)", line)
    if not m:
        return line

    func = m.group(2)
    file = m.group(3)
    
    prefix_search =  re.match("/src/harnesses/(.+?)/",file)

    if prefix_search:
        if not prefix_search.group(1) in source_paths:
            file = file[len(prefix_search.group(0)):]
        else:
            file = file.removeprefix("/src/harnesses/")
        
    for source in source_paths:
        if source in file:
            ind = file.index(source)
            file = file[ind+len(source)+1:]
            break
    return f"{m.group(1)} {func} {file}{m.group(4)}"


def parse_java_line(line: str):
    m = re.match(".*at (.*)\\.(.*)\\((.*:.*)\\)", line)

    if not m:
        return [], []

    identifier = m.group(1)
    if "java.base" in identifier:
        return [], []
    func = m.group(2)
    file_name = m.group(3)

    return [func], [file_name]


def msan_cwe(line: str):
    return "CWE-457" if "use-of-uninitialized-value" in line else "CWE-908"


def ubsan_cwe(line: str):
    line = line.lower()
    if "integer overflow" in line:
        return "CWE-190"
    elif "division by zero" in line:
        return "CWE-369"
    elif "shift exponent" in line:
        return "CWE-1335"
    return "CWE-20"  # generic undefined behavior tag


def kfence_cwe(line: str):
    return "CWE-120"  # generic buffer overflow issue


def asan_cwe(line: str):
    line = line.lower()
    if "use-after-free" in line:
        return "CWE-416"
    elif "stack" in line:
        return "CWE-122"
    elif "heap" in line:
        return "CWE-121"
    elif "fpe" in line:
        return "CWE-369"
    elif "segv" in line:
        return "CWE-476"
    else:
        return "CWE-120"  # generic buffer overflow issue


def kasan_cwe(line: str):
    if "stack" in line:
        return "CWE-122"
    elif "heap" in line:
        return "CWE-121"
    else:
        return "CWE-120"  # generic buffer overflow issue


def c_err(sanitizer_name: str, line: str):
    print(line)
    if "AddressSanitizer" in sanitizer_name or "KASAN" in sanitizer_name:
        return re.match(".* ((?:KASAN|AddressSanitizer): .*?) ", line).group(1).strip()
    else:
        return sanitizer_name


def java_err(sanitizer_name: str, line: str):
    return sanitizer_name


def asan_desc(line: str):
    line = line.lower()
    if "use-after-free" in line:
        return "use after free error"
    elif "stack" in line:
        return "stack based buffer overflow"
    elif "heap" in line:
        return "heap based buffer overflow"
    elif "fpe" in line:
        return "divide by zero error"
    elif "segv" in line:
        return "null pointer dereference"
    else:
        return "buffer overflow"  # generic buffer overflow issue


def ubsan_desc(line: str):
    if "integer overflow" in line:
        return "integer overflow"
    elif "division by zero" in line:
        return "divide by zero error"
    elif "shift exponent" in line:
        return "incorrect bitwise shift"
    return "improper input validation"  # generic undefined behavior tag


tokens = {
    "KASAN": (
        "BUG: KASAN",
        "=======================================",
        lambda line: "KASAN memory issue",
        kasan_cwe,
        c_err,
        parse_c_line,
        fix_paths_c,
    ),
    "KFENCE": (
        "BUG: KFENCE",
        "=======================================",
        lambda line: "KFENCE memory issue",
        kfence_cwe,
        c_err,
        parse_c_line,
        fix_paths_c,
    ),
    "MemSan": (
        "MemorySanitizer",
        "Exiting",
        lambda line: "Memory sanitizer error",
        msan_cwe,
        c_err,
        parse_c_line,
        fix_paths_c,
    ),
    "AddressSanitizer": (
        "AddressSanitizer: ",
        "==ABORTING",
        asan_desc,
        asan_cwe,
        c_err,
        parse_c_line,
        fix_paths_c,
    ),
    "UBSAN": (
        "runtime error",
        "runtime error",
        ubsan_desc,
        ubsan_cwe,
        c_err,
        parse_c_line,
        fix_paths_c,
    ),
    "Assertion": (
        "Assertion",
        "failed",
        lambda line: "Assertion Failure",
        lambda line: "CWE-617",
        c_err,
        parse_c_line,
        fix_paths_c,
    ),
    "NamingContextLookup": (
        "Remote JNDI Lookup",
        "== libFuzzer crashing input ==",
        lambda line: "JNDI Naming context lookuop",
        lambda line: "CWE-77",
        java_err,
        parse_java_line,
        identity,
    ),
    "ExpressionLanguageInjection": (
        "ExpressionLanguageInjection",
        "== libFuzzer crashing input ==",
        lambda line: "Expression Language Injection",
        lambda line: "CWE-77",
        java_err,
        parse_java_line,
        identity,
    ),  # TODO
    "ServerSideRequestForgery": (
        "Server Side Request Forgery",
        "== libFuzzer crashing input ==",
        lambda line: "Server Side Request Forgery",
        lambda line: "CWE-918",
        java_err,
        parse_java_line,
        identity,
    ),
    "OSCommandInjection": (
        "OS Command Injection",
        "== libFuzzer crashing input ==",
        lambda line: "OS command Injection",
        lambda line: "CWE-78",
        java_err,
        parse_java_line,
        identity,
    ),
    # TODO - generic cwe id
    "Deserialization": (
        "Remote Code Execution",
        "== libFuzzer crashing input ==",
        lambda line: "Remote Code Execution",
        lambda line: "CWE-502",
        java_err,
        parse_java_line,
        identity,
    ),
    "FileReadWrite": (
        "File read/write hook",
        "== libFuzzer crashing input ==",
        lambda line: "Unauthorized File acccess",
        lambda line: "CWE-918",
        java_err,
        parse_java_line,
        identity,
    ),
    "IntegerOverflow": (
        "Integer Overflow",
        "== libFuzzer crashing input ==",
        lambda line: "Integer overflow",
        lambda line: "CWE-190",
        java_err,
        parse_java_line,
        identity,
    ),
    # TODO - There are two serializations defined, possibly this is not correct
    "FileSystemTraversal": (
        "File read/write hook",
        "== libFuzzer crashing input ==",
        lambda line: "Unauthorized Filesystem traversal",
        lambda line: "CWE-22",
        java_err,
        parse_java_line,
        identity,
    ),
    "LdapInjection": (
        "LDAP Injection",
        "== libFuzzer crashing input ==",
        lambda line: "LDAP Injection",
        lambda line: "CWE-77",
        java_err,
        parse_java_line,
        identity,
    ),
}

# print("HI!")
selected_sanitizers = {}
for sanitizer in md["sanitizers"]:
    sanitizer_name = sanitizer["name"]
    for sanitizer_type in tokens.keys():
        if (
            sanitizer_type in sanitizer_name
            or tokens[sanitizer_type][0] in sanitizer_name
        ) and sanitizer_type not in selected_sanitizers:
            selected_sanitizers[sanitizer_type] = (sanitizer, tokens[sanitizer_type])


# assert("AddressSanitizer" in md["sanitizers"][0])
# START_TOKEN, END_TOKEN, simple_error = tokens["AddressSanitizer"]

in_san_depth = 0

current_extractor = lambda line: ([], [])
current_finalizer = ""
current_path_fixer = id
simple_error = ""
starter = """I found a crash. I think it is a(n) {simple_error}. Can you fix it please? The CWE Identifier is {cwe_id}.
```"""

lines = []
cwe_id_list = []
sanitizer_list = []
tiebreaker_functions = []
tiebreaker_files = []

# print(outlines)

if len(selected_sanitizers) == 0:
    print("ERROR: No sanitizer selected")
else:
    for line in outlines:
        if in_san_depth > 0:
            # line = line.replace(" /src"," {cp_path}/src")
            # If you want to try removing the timestamps
            # line = re.sub(r"^\[\s+\d+.\d+\]", "", line)
            lines.append(current_path_fixer(line) + "\n")

            new_functions, new_files = tiebreaker_extractor(line)

            tiebreaker_functions += new_functions
            tiebreaker_files += new_files

            if current_finalizer in line:
                in_san_depth -= 1
                lines.append("```")
        else:
            for sanitizer_name, (
                internal_sanitizer,
                (
                    START_TOKEN,
                    END_TOKEN,
                    desc_extractor,
                    cwe_id_extractor,
                    sanitizer_extractor,
                    tiebreaker_extractor,
                    path_fixer,
                ),
            ) in selected_sanitizers.items():
                if START_TOKEN in line:
                    sanitizer_list.append(internal_sanitizer)
                    in_san_depth += 1
                    current_finalizer = END_TOKEN
                    current_path_fixer = path_fixer
                    simple_error = desc_extractor(line)
                    cwe_ids = cwe_id_extractor(line)
                    cwe_id_list.append(cwe_ids)
                    lines.append(
                        starter.format(
                            simple_error=simple_error, cwe_id=" or ".join(cwe_id_list)
                        )
                    )
                    # line = line.replace(" /src"," {cp_path}/src")
                    lines.append(path_fixer(line) + "\n")

# os.makedirs(os.path.dirname(output))

with open(join(output, "sanitizer.json"), "w") as f:
    f.write(json.dumps(sanitizer_list))

with open(join(output, "cwe_id.json"), "w") as f:
    f.write(json.dumps(cwe_id_list))

with open(join(output, "report.txt"), "w") as f:
    f.writelines(lines)

with open(join(output, "tiebreaker_files.json"), "w") as f:
    f.writelines(json.dumps(tiebreaker_files))

with open(join(output, "tiebreaker_functions.json"), "w") as f:
    f.writelines(json.dumps(tiebreaker_functions))
