import logging
from typing import List, Union
import litellm
import os
import sys
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)

# Dependencies:
# 1. Install python3.8
# 2. Install litellm package

#######
# Some configurations
#######
litellm_model = (
    "oai-gpt-4o" if os.getenv("AIXCC_CRS_SCRATCH_SPACE", False) else "gpt-4o-2024-05-13"
)

root_dir = Path(__file__).parent

g4_database = root_dir.joinpath("grammars")


# For prompt construction
test_harness_file = sys.argv[1]
example_g4_file = root_dir.joinpath("grammars", "http", "http.g4")

out_g4 = sys.argv[2]
# For matching the pit file
subject_name = sys.argv[3]

# For checking the correctness of the pit file
initial_testcases = sys.argv[4] if len(sys.argv) > 4 else None

# The pit file generated by LLM
llm_pit_file = root_dir.joinpath("intermediary_grammar.g4")
trial_times = 5


def construct_g4_generation_prompt(test_harness: str, example_pit: str) -> str:
    return (
        "Generate an ANTLR4 g4 file without actons for the following test harness.\n"
        f"```c {test_harness}```\n\n"
        "For your reference, here is an example of an ANTLR g4 file for the HTTP input.\n"
        f"```g4 {example_pit}```\n"
    )


def request_llm_generation_helper(times: int) -> str:
    # Step 1: generate the inital pit file using LLM
    test_harness = open(test_harness_file, "r").read()
    example_g4 = open(example_g4_file, "r").read()
    prompt = construct_g4_generation_prompt(test_harness, example_g4)

    logging.debug(prompt)

    messages = [
        {
            "role": "system",
            "content": "You are an expert programmer in the ANTLR4 grammar g4 file format.",
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    key = os.getenv("LITELLM_KEY", None)
    response = litellm.completion(
        model=litellm_model,
        messages=messages,
        temperature=0.8,
        top_p=1,
        base_url=os.getenv("AIXCC_LITELLM_HOSTNAME", None),
        extra_headers={"Authorization": f"Bearer {key}"} if key else {},
        custom_llm_provider="openai",
    )
    print(response)
    content = response.choices[0].message.content
    content = content.split("```g4")[1].split("```")[0].strip()
    # For debugging
    with open("init_pit.xml", "w") as f:
        f.write(content)

    # Step 2: LLM self-corrects the pit file, as the generation from the first round is slightly incorrect
    messages = [
        {
            "role": "system",
            "content": "You are an expert programmer in the ANTLR4 g4 file format.",
        },
        {
            "role": "user",
            "content": prompt,
        },
        {
            "role": "assistant",
            "content": content,
        },
        {
            "role": "user",
            "content": "Do you satisfy all the requirements? Please correct and generate the Peach pit file.",
        },
    ]

    response = litellm.completion(
        model=litellm_model,
        messages=messages,
        temperature=0.8,
        top_p=1,
        base_url=os.getenv("AIXCC_LITELLM_HOSTNAME", None),
        extra_headers={"Authorization": f"Bearer {key}"} if key else {},
        custom_llm_provider="openai",
    )
    content = response.choices[0].message.content
    content = content.split("```xml")[1].split("```")[0].strip()

    with open(llm_pit_file, "w") as f:
        f.write(content)

    # cp init_kernel_pit.xml to init_kernel_pit_{times}.xml
    os.system(f"cp init_g4.g4 init_g4_{times}.xml")
    os.system(f"cp {llm_pit_file} intermediary_g4_{times}.xml")
    return llm_pit_file


def check_g4_correctness(pit_file: str) -> bool:
    # check whether the pit file matches the example test cases
    # execute the command: peach -1 -inputFilePath=example_testcases -outputFilePath=dummy pit_file

    if initial_testcases is None:
        return True

    return False

    # command = f"/hone/ubuntu/peach-cracker/output/linux_x86_64_release/bin/peach -1 -inputFilePath={initial_testcases} -outputFilePath=dummy {pit_file}"
    # result = subprocess.run(
    #     command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    # )
    # logging.debug(f"## Execution result: {result.stdout}")
    # # check if result.stdout contains "\nok\n\n"
    # res = result.stdout.find("\nok\n\n")
    # if res >= 0:
    #     logging.debug(f"## The pit file is correct.")
    #     return True
    # else:
    #     logging.debug(f"## The pit file is incorrect.")
    #     return False


def request_llm_generation():
    for times in range(trial_times):
        g4_file = request_llm_generation_helper(times)
        if check_g4_correctness(g4_file):
            return g4_file
    return None


import random


def select_winner(g4_list, test_harness):
    prompt = (
        f"For the subject {subject_name} with the following test harness, in the list of ANTLR4 g4 files {g4_list},"
        f"do you think whether there is a matched grammar? If you ARE NOT CONFIDENT, please say 'None'; otherwise, return the name of the matched one surrounded in ```:\n\n"
        f"```c {test_harness}```\n NO YAPPING \n"
    )

    logging.debug(f"Prompt to check pit correctness:\n {prompt}")
    checking_message = [
        {
            "role": "system",
            "content": "You are an expert programmer in the ANTLR4 g4 file format.",
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]
    key = os.getenv("LITELLM_KEY", None)
    response = litellm.completion(
        model=litellm_model,
        messages=checking_message,
        temperature=0.8,
        top_p=1,
        base_url=os.getenv("AIXCC_LITELLM_HOSTNAME", None),
        extra_headers={"Authorization": f"Bearer {key}"} if key else {},
        custom_llm_provider="openai",
    )
    real_answer = response.choices[0].message.content

    if "none" in real_answer.lower():
        return None

    fragments = real_answer.split("```")

    filtered_answer = fragments[1].strip() if len(fragments) > 1 else None
    logging.debug(f"LLM answer: {real_answer}")
    logging.debug(f"LLM filtered answer: {filtered_answer}")
    return filtered_answer


def tournament(candidates, test_harness, group_size=10):
    while len(candidates) > 2:
        next_round = []
        for i in range(0, len(candidates), group_size):
            group = candidates[i : i + group_size]
            winner = select_winner(group, test_harness)
            next_round.append(winner)
        candidates = next_round
    return candidates


def llm_check_g4_correctness() -> Union[List[str], None] :
    # Based on the subject name and the test harness, we can construct a prompt
    # and ask LLM which pit file is the best match
    test_harness = open(test_harness_file, "r").read()
    # print(f"Listing {g4_database}")
    g4_list = os.listdir(g4_database)

    candidates = tournament(g4_list, test_harness)
    print(f"Candidates are {candidates}")
    if len(candidates) == 0 or candidates[0] == None:
        return None
    candidate = g4_database.joinpath(candidates[0])
    print(f"got candidate {candidates[0]}")

    if candidate.exists():
        return candidate
    else:
        return None


def check_g4_from_database() -> str:
    if initial_testcases is None:
        # If no initial seeds, we delegate the task to LLM
        res = llm_check_g4_correctness()
        return res

    # else:
    #     # traverse each pit file in the database directory
    #     for g4_file in os.listdir(g4_database):
    #         pit_file_path = os.path.join(g4_database, g4_file)
    #         logging.debug(f"Checking pit file: {pit_file_path}")
    #         if check_pit_correctness(pit_file_path):
    #             return pit_file_path

    return None


def main():
    # Step 1: Check the database for a matching pit file
    g4_dir = check_g4_from_database()

    # Step 2: If the pit file is not found, use LLM to generate the pit file
    if g4_dir is None:
        g4_dir = request_llm_generation()
        logging.debug("No matching pit file found in the database.")
    else:
        logging.debug(f"Found the matching pit file: {g4_dir}")

    os.system(f"cp -rf {g4_dir} {out_g4}")
    return


if __name__ == "__main__":
    main()
