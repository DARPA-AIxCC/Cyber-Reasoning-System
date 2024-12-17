from typing import Callable
import re
import subprocess as sp
import argparse
import json
import os
import shlex
from enum import Enum
import sys
import time
import random
import tempfile

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DIR =  tempfile.TemporaryDirectory(prefix="dd_tmp_",ignore_cleanup_errors=True)

MOCK_PROJECT = False

#  an enum class for patch type
class PatchType(Enum):
    DELETION = 1
    INSERTION = 2


def parse_changed_line(change:str):
    # '-71,7' or '+71,15'
    # change =  change[1:].split(",")
    start_line = int(change[1:].split(",")[0])
    line_count = int(change[1:].split(",")[1])
    return start_line , line_count   


def post_process_patch(diff_patch_text:str, relative_file_name:str):
    '''
    Replace file paths in the diff patch with relative file names
    '''
    patch_lines = diff_patch_text.split("\n")    
    
    for idx in range(len(patch_lines)):
        if patch_lines[idx].startswith("diff --git "):
            # use the relative file name
            patch_lines[idx] = f"diff --git a/{relative_file_name} b/{relative_file_name}"
            patch_lines[idx+2] = f"--- a/{relative_file_name}"  
            patch_lines[idx+3] = f"+++ b/{relative_file_name}"
    
    return "\n".join(patch_lines)   


def form_diff_patch(line_patch_list, project_dir):

    project_tmp_dir = os.path.join(TMP_DIR.name)
    if not os.path.exists(project_tmp_dir):
        os.makedirs(project_tmp_dir)    
    
    patch_dict = {}
    i = 0
    for patch_tuple in line_patch_list:
        i+=1
        filename = patch_tuple[1]
        if filename not in patch_dict:
            patch_dict[filename] = []
        patch_dict[filename].append(patch_tuple)


    diff_patch_list = []

    for filename in patch_dict:
        
        # get the current code and apply the patch
        current_file = os.path.join(project_dir, filename)  
        if not os.path.exists(current_file):
            print("File not found:", current_file)
            continue

        with open(current_file, "r") as f:
            lines = f.readlines()

        for patch_tuple in patch_dict[filename]:
            line_number = patch_tuple[2]
            patch_type = patch_tuple[3]
            new_code = patch_tuple[0]
            if patch_type == PatchType.DELETION:
                lines[line_number-1] = ""
            elif patch_type == PatchType.INSERTION:
                if not lines[line_number-1].endswith("\n") and lines[line_number-1] != "":
                    lines[line_number-1] += "\n"   
                if not new_code.endswith("\n"):
                    new_code += "\n"    
                lines[line_number-1] += new_code


        tmp_file = os.path.join(project_tmp_dir, filename.replace("/", "__"))
        with open(tmp_file, "w") as f:
            f.writelines(lines)

        patch_file = f"{tmp_file}.patch"
        if os.path.exists(patch_file):
            os.remove(patch_file)

        # generate the diff patch by comparing the current file and the tmp file
        cmd = f"git diff --no-index --patch --output={patch_file} {current_file} {tmp_file}" # old_file new_file  
        try:  
            sp_result = sp.run(cmd, check=True, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
            with open(patch_file, "r") as f:
                diff_patch_list.append(post_process_patch(f.read(), filename))
        except sp.CalledProcessError as e:
            if os.path.exists(patch_file):
                with open(patch_file, "r") as f:
                    
                    diff_patch_list.append(post_process_patch(f.read(), filename))
        
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
        if os.path.exists(patch_file):  
            os.remove(patch_file)
        
        
            
        
    patch_txt = "\n".join(diff_patch_list)    
    if not patch_txt.endswith("\n"):
        patch_txt += "\n"

    return patch_txt

def ddmin(test:Callable, inp:list, project_dir:str , *test_args) -> list:
    """Reduce the input inp, using the outcome of test(fun, inp)."""
    assert test([], project_dir) == 0 # current code triggers the failure

    n = 2     # Initial granularity
    while len(inp) >= 2:
        print(f"granularity {n}")
        start = 0
        subset_length = int(len(inp) / n)
        if_pass = False

        while start < len(inp):
            complement = (inp[:int(start)] + inp[int(start + subset_length):])

            if test(complement, project_dir): # If the test passes
                inp = complement
                n = max(n - 1, 2)
                if_pass = True
                break

            start += subset_length

        if not if_pass:
            if n == len(inp):
                break
            n = min(n * 2, len(inp))

    return inp
    
def get_line_patch_list(diff_patch_text: str) -> list:

    '''
    This function parse the git diff and return a list of tuples"
        (code, filename, line_number, patch_type)       
    '''
    patch_lines = diff_patch_text.split("\n")
    changed_files_before = []
    changed_files_after = []
    code_hunk_lines = []
    # filename: {(start_line, line_count) : code}
    for idx, line in enumerate(patch_lines):
        if line.startswith("diff --git"):
            # 'a/django/contrib/auth/forms.py' remove the first two characters 
            file_name_a = line.split(" ")[2][2:]
            file_name_b = line.split(" ")[3][2:]   
            changed_files_before.append(file_name_a) 
            changed_files_after.append(file_name_b)

        if line.startswith("@@"):   
            # print("AFFECTED:",line)

            last_changed_file_before = changed_files_before[-1]    
            last_changed_file_after = changed_files_after[-1]
            # if last_changed_file_after not in code_hunk_before:
            #     code_hunk_before[last_changed_file_after] = {}
            before_line = line.split(" ")[1]
            after_line = line.split(" ")[2]
            before_line_start_line, before_line_count = parse_changed_line(before_line)
            after_line_start_line, after_line_count = parse_changed_line(after_line)      

            inspected_line_number_before = -1
            inspected_line_number_after = -1
    
            last_original_line_number = before_line_start_line -1
            for inspect_line in patch_lines[idx+1:]:

                if not inspect_line.startswith("+"):
                    inspected_line_number_before += 1

                if not inspect_line.startswith("-"):
                    inspected_line_number_after += 1                
                
                if inspect_line.startswith("+"):
                   print(inspect_line[1:])
                   code_hunk_lines.append( (inspect_line[1:], last_changed_file_before, last_original_line_number, PatchType.INSERTION)  )

                   # insert after the line last_original_line_number
                
                elif inspect_line.startswith("-"):

                    print(inspect_line[1:])
                    code_hunk_lines.append( (inspect_line[1:], last_changed_file_before, before_line_start_line+inspected_line_number_before ,PatchType.DELETION)  )

                    # delete line at  before_line_start_line+inspected_line_number

                if not inspect_line.startswith("+"):
                    last_original_line_number += 1

                if inspected_line_number_before == before_line_count-1 and inspected_line_number_after == after_line_count-1:
                    break

    return code_hunk_lines

            

# lang_tokens = ['(', ')', '[', ']', '.', ',', '&', '*', '+', '~', '!', '/', '%', '<<', '>>', '<=', '>=', '==', '>', '<', '^', '|', ':', ';', '=', '{', '}', 'if', 'for', 'while', 'switch', 'return']

# '&&', '||', '<<', '>>', '<=', '>=', '==',
def text_to_special(diff_patch_text):
    new_lines = []
    for line in diff_patch_text.splitlines():
        if line[0] == '+':
            line = line[1:]
            lexed = shlex.shlex(line)    
            lexed_token = lexed.get_token()
            lexed_tokens = []
            red_str = line
            while lexed_token is not None and lexed_token is not "":
                i = red_str.find(lexed_token)
                pre_str = red_str.split(lexed_token)[0]
                red_str = red_str[i:]

                if len(pre_str) >= 1:
                    lexed_tokens += [pre_str]
                lexed_tokens += [lexed_token]
                red_str = red_str[len(lexed_token):]
                lexed_token = lexed.get_token()
     
            special_lines = [f"+<SPECIAL_LINE>{l}" for l in lexed_tokens]
            new_lines +=  special_lines 
        else:
            new_lines += [ line ]
    return ("\n".join(new_lines))

def special_to_text(special):
    new_lines = []
    new_line = []
    app = 0
    for line in special.splitlines():
        if line.startswith("+<SPECIAL_LINE>"):
            app += 1
            new_line.append(line[len("+<SPECIAL_LINE>"):])
        elif app > 0:
            new_lines.append("+" + "".join(new_line))
            new_line = []
            new_lines += [line]
            app = 0
        else:
            new_lines += [line]

    return ("\n".join(new_lines))


def delta_debugging(patch_text: str, test_fn : Callable, project_dir:str) -> list:
    print("Begin")
    patch_list = get_line_patch_list(patch_text)
    print(f"Got patch list with {len(patch_list)} patches")
    reduced_patch_list = ddmin(test_fn, patch_list, project_dir, None)
    print(f"Reduced patch list to {len(reduced_patch_list)} patches")
    return form_diff_patch(reduced_patch_list, project_dir)

        
def reset_head(cp_src):
    sp.run(f"cd {cp_src}; git checkout -- .", shell=True)

def apply(patch_diff_list, cp_src):
    patch_text = form_diff_patch(patch_diff_list, cp_src)   

    f = open(f"{cp_src}/healing-touch-patch-temp.diff", "w")
    f.write(patch_text)
    f.close()
    print("wrote")

    p = sp.run(f"cd {cp_src}; git apply healing-touch-patch-temp.diff", shell=True)
    return p.returncode == 0
   
def mutate_special(special, count_only=False):
    un_ops = ['~', '!']    
    bin_ops = ['*', '+', '/', '%', '&', '^', '<<', '>>'] 
    cmp_ops = ['<', '>', '<=', '>=', '==', '||', '&&']

    if not count_only:
        total = mutate_special(special, count_only=True)
        index = random.randint(0, total-1)

    new_lines = []
    mutation_indices = 0
    for line in special.splitlines():
        new_line = line

        if not line.startswith('+<SPECIAL_LINE>'):
            new_lines += [new_line]
            continue

        lp = line[len('+<SPECIAL_LINE>'):]
        l = lp.strip()

        if l in bin_ops:
            if not count_only and mutation_indices == index:
                new_line = "+<SPECIAL_LINE>" + lp.replace(l, random.choice(bin_ops))
                print(f'"{line}" --> "{new_line}"')
            mutation_indices += 1
        elif l in un_ops:
            if not count_only and mutation_indices == index:
                new_line = "+<SPECIAL_LINE>" + lp.replace(l, "")
                print(f'"{line}" --> "{new_line}"')
            mutation_indices += 1
        elif l in cmp_ops:
            if not count_only and mutation_indices == index:
                new_line = "+<SPECIAL_LINE>" + lp.replace(l, random.choice(cmp_ops))
                print(f'"{line}" --> "{new_line}"')
            mutation_indices += 1
        elif l.isnumeric():
            if not count_only and mutation_indices == index:
                new_line = "+<SPECIAL_LINE>" + lp.replace(l, str(random.choice([0, 1, int(l) + 1, int(l) - 1, 2**32, 2**64])))
                print(f'"{line}" --> "{new_line}"')
            mutation_indices += 1
        elif l.isdecimal():
            if not count_only and mutation_indices == index:
                new_line = "+<SPECIAL_LINE>" + lp.replace(l, str(random.choice([0, 2**32, 2**64])))
                print(f'"{line}" --> "{new_line}"')
            mutation_indices += 1
        elif l.startswith('"') and l.endswith('"'):
            if not count_only and mutation_indices == index:
                new_line = "+<SPECIAL_LINE>" + lp.replace(l, l[0:len(l)-2])
                print(f'"{line}" --> "{new_line}"')
            mutation_indices += 1
        elif l.startswith("'") and l.endswith("'"):
            if not count_only and mutation_indices == index:
                new_line = "+<SPECIAL_LINE>" + lp.replace(l, random.choice(string.ascii_uppercase + string.digits))
                print(f'"{line}" --> "{new_line}"')
            mutation_indices += 1
        new_lines += [new_line]

    if count_only: 
        return (mutation_indices)
    else:
        return "\n".join(new_lines)

env_prefix = os.environ.copy()
if __name__ == "__main__":

    parser = argparse.ArgumentParser(
                        prog='DD-Repair',
                        description='Delta-Debugging Repair',
                    )

    parser.add_argument('meta_data')           
    parser.add_argument('-o', '--out', default="out.diff")

    args = parser.parse_args()

    f = open(args.meta_data)
    s = f.read()
    f.close()
    md = json.loads(s)

    cp_src = md["cp_src"]
    cp_path = md["cp_path"]
    
    if not MOCK_PROJECT:

        reset_head(cp_src)
        validate_script = md["validate_script"]
        build_script = md["build_script"]

        bug_intro_commit = md["commit"]

        p = sp.run(f"cd {cp_src}; git rev-list --parents -n 1 {bug_intro_commit}",
            shell=True,
            capture_output=True,
            check=True)
        last_good_commit = p.stdout.decode("utf-8").split(" ")[1]

        p = sp.run(f"cd {cp_src}; git diff HEAD {last_good_commit}",
            shell=True,
            capture_output=True,
            check=True)
        diff_patch_text = p.stdout.decode("utf-8")

        def test(patch_diff_list, cp_src):
            global env_prefix
            # Return true if project builds and is non-crashing
            if not apply(patch_diff_list, cp_src):
                return 0

            p = sp.run(build_script, shell=True, env=env_prefix)
            if p.returncode != 0:
                reset_head(cp_src)
                return 0
            p = sp.run(validate_script, shell=True, env=env_prefix)
            if p.returncode != 0:
                reset_head(cp_src)
                return 0

            reset_head(cp_src)
            return 1

        start = time.time()
        r = test(get_line_patch_list(diff_patch_text), cp_src)
        end = time.time()

        timeout_secs = int(end - start)
        env_prefix["HT_TIMEOUT"] = f"{timeout_secs}s"
        if not r:
            print("not using unit tests")
            env_prefix["NO_FUNC"] = "1"

        r = test(get_line_patch_list(diff_patch_text), cp_src)
        reset_head(cp_src)

    elif MOCK_PROJECT:
        reset_head(cp_src)
        # TEST CASE 1:
        # test_file = "diff_log.log"
        # test_commit = https://github.com/jenkinsci/jenkins/commit/e5046911c57e60a1d6d8aca9b21bd9093b0f3763
        # test_file = "diffs/diff_log2.log"
        # TEST CASE 2:
        # test_commit2 =https://github.com/jenkinsci/jenkins/commit/2c02654e9c032dc0e1b5d3ea98477c8731197a6a
        test_file = "diffs/diff_log3.log"
        with open(test_file, "r") as f:
            diff_patch_text = f.read()

        def test(patch_diff_list, cp_src):
            FLAG = 0 
            for patch in patch_diff_list:
                if "The subtitle for the application bar" in patch[0]:
                    FLAG += 1
                if "margin-bottom: var(--section-padding);" in patch[0]:
                    FLAG += 1
        
            if FLAG == 2:
                return 1
            else:
                return 0
        

    reduced_patch = delta_debugging(diff_patch_text, test, project_dir=cp_src)    
    # reduced_patch = diff_patch_text    
    patches = [reduced_patch]

    def test_special(special_as_list, cp_src):
        special_patch_text = form_diff_patch(special_as_list, cp_src)
        text = special_to_text(special_patch_text)
        lines = get_line_patch_list(text)
        return test(lines, cp_src)
        
    special_reduced = text_to_special(reduced_patch)
    lex_reduced_patch = delta_debugging(special_reduced, test_special, project_dir=cp_src)    
    lex_reduced_patch = special_to_text(lex_reduced_patch)
    lines = get_line_patch_list(lex_reduced_patch)
    lex_reduced_patch = form_diff_patch(lines, cp_src)   

    print(lex_reduced_patch)

    patches += [lex_reduced_patch]
    for i in range(20):
        try:
            print("mutating...")
            new = mutate_special(text_to_special(lex_reduced_patch))
            special = special_to_text(new)
            lines = get_line_patch_list(special)
            text = form_diff_patch(lines, cp_src)   
            patches += [text]
        except Exception as e:
            print(e)
            pass

    i = 0

    for patch in patches:
        with open(f"{args.out}{i}", "w") as f:
            f.write(patch)  
        i += 1


        
