from hermes.log import logger

from pathlib import Path
import subprocess
import shutil
import re


def apply_diff(diff_file, target_file):
    logger.info(f'Attempting to apply {diff_file} to {target_file}.')
    try:
        target_file = Path(target_file)
        patched_file = target_file.stem + '_patched.txt'
        shutil.copy(target_file, patched_file)
        subprocess.run(
            ['patch', patched_file, diff_file],
            check=True, text=True, capture_output=True
        )

        logger.info(f'Patch applied to: {patched_file}')
        return Path(patched_file)
    except subprocess.CalledProcessError as e:
        logger.warning(f'An error occurred while applying the patch: {e}')
        # print("stdout:", e.stdout)
        # print("stderr:", e.stderr)

def process_diff(diff):
    logger.info('Attempting to extract file_name and line numbers from diff.')
    if isinstance(diff, str):
        lines = diff.splitlines()
    if isinstance(diff, list):
        lines = diff
    else:
        raise TypeError(
            'Input diff is supposed to be a list or string. '
            f'Got {type(diff)} instead.'
        )

    pattern = r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@"
    line_numbers = []

    first_file_name = ''
    second_file_name = ''
    file_name = ''

    for line in lines:
        if line.startswith('---'):
            first_file_name = line.replace('--- ', '')
            # first_file_name = "/".join(first_file_name.split("/")[1:])
            first_file_name = Path(*Path(first_file_name).parts[1:])
        elif line.startswith('+++'):
            second_file_name = line.replace('+++ ', '')
            # second_file_name = "/".join(second_file_name.split("/")[1:])
            second_file_name = Path(*Path(second_file_name).parts[1:])
        matches = re.findall(pattern, line)
        if matches:
            for match in matches:
                original_start = int(match[0])
                line_numbers.append(original_start)

    if not first_file_name and not second_file_name:
        logger.warning('Could not find file name.')
    else:
        if first_file_name == second_file_name:
            file_name = first_file_name
        else:
            logger.warning('File name on +++ and --- does not match.')
    logger.info(f'Success! Provided diff points to: {file_name}.')
    return {
        'file_name': file_name,
        'line_numbers': line_numbers
    }
