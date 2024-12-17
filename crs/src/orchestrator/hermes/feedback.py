import sys

try:
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    raise ImportError("pysqlite3 module is required to replace sqlite3.")

from hermes.core.utils.metadata import MetadataUtils
from hermes.core.utils.patching import process_diff, apply_diff
from hermes.config.pipelines import FeedbackConfig, TestConfig

from hermes.core.program import Program
from hermes.core.preprocess import Preprocessor

from hermes.core.tasks import BugDescriber, CWEDescriber, Fixer

from hermes.log import logger

from pathlib import Path
import argparse
import json


def run(input_path, use_test=False, quiet=False, num_patches=5):
    if use_test:
        logger.info('Using test config.')
        config = TestConfig
    else:
        logger.info('Using production config.')
        config = FeedbackConfig

    CWE_DESCRIBERS = config.get_predescription_models()
    BUG_DESCRIBERS = config.get_description_models()
    REPAIR_MODELS = config.get_repair_models()

    with open(input_path, 'r') as file:
        input_file = json.load(file)

    base_dir = Path(input_file.get('base_dir', Path.cwd()))
    output_dir = Path(input_file['output_dir'])

    cwe_id = input_file.get('cwe_id', '')
    if not cwe_id:
        raise ValueError('Could not find cwe_id.')

    language = input_file.get('language', '')
    if not language:
        raise ValueError('Could not find language.')

    patch_list = input_file['patches']

    # Setup output directories
    directories = MetadataUtils.setup_directories(
        output_dir=output_dir,
        base_dir=base_dir
    )
    source_dir = directories['source_dir']

    description_prompt_dir = directories['description_prompt_dir']
    repair_prompt_dir = directories['repair_prompt_dir']

    description_dir = directories['description_dir']
    patch_dir = directories['patch_dir']
    raw_patch_dir = directories['raw_patch_dir']

    # Get supported patch types
    supported_patch_types = MetadataUtils.get_supported_patch_types()

    all_patches = []
    for patch_data in patch_list[:num_patches]:
        logger.info(f'Processing {len(patch_list)} patches.')

        original_description = patch_data.get('description', '')

        cost = {}
        # Build Program object for original program
        if original_description:
            logger.info('Found description of original bug.')

            source_path = Path(
                Path(base_dir) / patch_data.get('source_path', '')
            )
            if not source_path:
                raise ValueError('Could not find source_path.')

            line_number = patch_data.get('line_number', '')
            if not line_number:
                raise ValueError('Could not find line_number.')

            patch_content = '\n'.join(patch_data.get('patch_content', ''))
            if not patch_content:
                raise ValueError('Could not find patch_content.')

            preprocessor = Preprocessor(
                file_path=source_path,
                cwe_id=cwe_id,
                language=language
            )
            original_program = preprocessor.process(line_number=line_number)
        else:
            logger.info('Description of original bug not given.')
            diff_file_name = patch_data['patch_file']
            diff_dir = input_file['patch_dir']
            diff_generator = patch_data['generator']
            diff_file_path = Path(
                Path(diff_dir) /
                diff_generator /
                diff_file_name
            )
            # diff_file_path = f"{diff_dir}/{diff_generator}/{diff_file_name}"
            with open(diff_file_path, 'r') as d_f:
                content = d_f.readlines()
                diff_text = [line.strip() for line in content[2:]]
            diff_data = process_diff(diff=diff_text)
            source_file = diff_data['file_name']
            source_path = Path(base_dir) / source_file
            line_numbers = diff_data['line_numbers']

            preprocessor = Preprocessor(
                file_path=source_path,
                cwe_id=cwe_id,
                language=language
            )
            candidate_programs = [
                preprocessor.process(line_number=line_no)
                for line_no in line_numbers
            ]
            # Take only the first unique function
            original_program = list(set(candidate_programs))[0]
            # Apply buggy patch to source
            patched_source_path = apply_diff(
                diff_file=diff_file_path,
                target_file=source_path
            )
            # Create new Program object to get buggy patched function
            patch_preprocessor = Preprocessor(
                file_path=patched_source_path,
                cwe_id=cwe_id,
                language=language
            )
            patched_program = patch_preprocessor.process(
                line_number=original_program.line_number
            )
            # Store buggy patched function in patch_content
            patch_content = patched_program.processed_source

            pre_describer = CWEDescriber(
                input_program=original_program,
                description_prompt_dir=description_prompt_dir,
                description_dir=description_dir,
                description_models=CWE_DESCRIBERS,
                quiet=quiet
            )
            logger.info(
                'Generating new description for original vulnerability.'
            )
            original_description, \
                cost = pre_describer.get_descriptions(cost=cost)
            original_description = list(original_description.values())[0]
        if not quiet:
            # Write original processed vulnerable source to disk
            original_bug_path = (
                Path(source_dir) /
                f'{original_program.program_id}.processed_source'
            )
            MetadataUtils.write_file(
                text=original_program.processed_source,
                path=original_bug_path
            )

        patch_type = patch_data.get('patch_type', 'NOT_GIVEN')
        patch_file = patch_data.get('patch_file', '')

        if patch_type in supported_patch_types:
            # BugDescriber will describe why the bad patch is bad
            logger.info(
                f'Patch: {patch_file} has type {patch_type}, which '
                'is supported. Processing.'
            )
            describer = BugDescriber(
                input_program=original_program,
                original_description=original_description,
                buggy_patch=patch_content,
                patch_type=patch_type,
                description_prompt_dir=description_prompt_dir,
                description_dir=description_dir,
                description_models=BUG_DESCRIBERS,
                quiet=quiet
            )
            descriptions, cost = describer.get_descriptions(cost=cost)

            # Treat the buggy patch as a program to repair
            buggy_patch = Program(
                original_source=original_program.original_source,
                file_path=source_path,
                cwe_id=cwe_id,
                processed_source=patch_content,
                line_number=original_program.line_number
            )
            if not quiet:
                # Write original buggy patch to disk
                buggy_patch_path = (
                    Path(source_dir) / f'{patch_file}.original_patch'
                )
                MetadataUtils.write_file(
                    # Assuming that the processed source is the patch
                    text=buggy_patch.processed_source,
                    path=buggy_patch_path
                )

            fixer = Fixer(
                input_program=buggy_patch,
                neighbors=None,
                repair_models=REPAIR_MODELS,
                repair_prompt_dir=repair_prompt_dir,
                raw_patch_dir=raw_patch_dir,
                patch_dir=patch_dir,
                output_dir=output_dir,
                quiet=quiet
            )
            patches = fixer.get_patch(
                descriptions=descriptions,
                cost=cost
            )

            for patch in patches:
                all_patches.append(
                    MetadataUtils.process_patch(
                        input_program=buggy_patch,
                        describer_id=patch['describer_id'],
                        description=patch['description'],
                        fixer_id=patch['fixer_id'],
                        patch_lines=patch['patch'].lines,
                        patch_path=str(patch['patch_path'])
                    )
                )
        else:
            logger.info(
                f'{patch_file} has type {patch_type} '
                 'which is not supported.'
            )
    metadata_path = (
        Path(output_dir) / 'generated_feedback_patches.json'
    )
    metadata = {
        'language': language,
        'output_dir': str(output_dir),
        'patches': all_patches
    }
    MetadataUtils.dump_dict(data=metadata, path=metadata_path)

    return metadata

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input_path",
        help='Path to metadata JSON'
    )
    parser.add_argument(
        "num_patches",
        type=int,
        nargs='?',
        default=5,
        help='Number of patches to process'
    )
    parser.add_argument(
        '-t', '--test',
        action='store_true',
        dest='use_test',
        help='If passed, will use the test config (only one model per step).'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        dest='quiet',
        help='If passed, will not write intermediate outputs to disk.'
    )

    # Get args from CLI
    args = parser.parse_args()

    #   [str]: Location of metadata file to find locations
    input_path = args.input_path

    #   [int]: Number of patches to process (optional, by default 5)
    num_patches = args.num_patches

    #   [bool]: Should we use the test config?
    use_test = args.use_test

    #   [bool]: Should we suppress writing prompts and raw responses?
    quiet = args.quiet

    logger.info(
        f'Attempting to run using (input_path={input_path}, '
        f'use_test={use_test}, quiet={quiet}, num_patches={num_patches}).'
    )
    try:
        metadata = run(
            input_path=input_path,
            use_test=use_test,
            quiet=quiet,
            num_patches=int(num_patches)
        )
        logger.info(
            'Feedback mode produced '
            f'{len(metadata.get("patches", []))} patches.'
        )
    except Exception as e:
        logger.error(f'Running the tool produced {e}.')
