import sys

try:
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    raise ImportError("pysqlite3 module is required to replace sqlite3.")

import chromadb
from chromadb.config import Settings

from hermes.core.utils.metadata import MetadataUtils
from hermes.config.pipelines import HermesConfig, TestConfig
from hermes.log import logger

from hermes.core.preprocess import Preprocessor

from hermes.core.search import ChromaSearch

from hermes.config.config import CHROMA_PATH, COLLECTION_NAME, NUM_NEIGHBORS
from hermes.core.tasks import CWEDescriber, Fixer, Reviewer

from pathlib import Path
import argparse
import json



def run(input_path, use_test=False, quiet=False):
    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False)
    )
    collection = client.get_collection(name=COLLECTION_NAME)
    searcher = ChromaSearch(collection=collection)

    if use_test:
        logger.info('Using test config.')
        config = TestConfig
    else:
        logger.info('Using production config.')
        config = HermesConfig

    # Setup models from config
    DESCRIPTION_MODELS = config.get_description_models()
    REPAIR_MODELS = config.get_repair_models()
    REVIEW_MODELS = config.get_review_models()

    # Read metadata
    with open(input_path, 'r') as input_file:
        metadata = json.load(input_file)

    # Get source directory if it exists
    base_dir = Path(metadata.get('base_dir', Path.cwd()))

    output_dir = Path(metadata.get('output_dir', 'output'))
    cwe_id = metadata.get('cwe_id', None)
    language = metadata.get('language', None)

    # Setup output directories
    directories = MetadataUtils.setup_directories(
        output_dir=output_dir,
        base_dir=base_dir
    )
    # output_dir = directories['output_dir']
    source_dir = directories['source_dir']

    description_prompt_dir = directories['description_prompt_dir']
    repair_prompt_dir = directories['repair_prompt_dir']
    review_prompt_dir = directories['review_prompt_dir']

    description_dir = directories['description_dir']
    patch_dir = directories['patch_dir']
    raw_patch_dir = directories['raw_patch_dir']
    review_dir = directories['review_dir']

    all_patches = []
    # Augment locations using stack trace
    try:
        logger.info('Attempting to read stack trace info.')
        if metadata['stack_trace']:
            trace_locations = [
                    {
                        'source_path': trace.get('source_file', ''),
                        'line_number': trace.get('line', None)
                    }
                    for trace in metadata.get('stack_trace', [])
            ]
            trace_locations = [
                elem
                for elem in trace_locations
                if elem['source_path'] and elem['line_number']
            ]

            locations = metadata.get('localization', []) + trace_locations
            logger.info(
                f'Successfully added {len(trace_locations)} stack trace '
                f'locations to {len(metadata["localization"])} locations.'
            )
        else:
            logger.info('Stack trace not given. Will not augment.')
    except Exception as e:
        logger.warning(f'Augmenting locations raised {e}. '
                    f'Skipping.')
        locations = metadata.get('localization', [])

    logger.info(f'Collected {len(locations)} total locations.')

    candidate_programs = []
    for location_info in locations:
        source_path = base_dir / Path(location_info.get('source_path', ''))
        line_number = location_info.get('line_number', None)
        program_id = str(source_path.stem) + f'_Line-{line_number}'
        preprocessor = Preprocessor(
            file_path=source_path,
            cwe_id=cwe_id,
            language=language,
            program_id=program_id
        )
        candidate_programs.append(
            preprocessor.process(line_number=line_number)
        )

    unique_programs = list(set(candidate_programs))
    logger.info(
        f'Found {len(unique_programs)} unique locations '
        f'from {len(candidate_programs)} original locations.'
    )

    valid_programs = [
        program
        for program in unique_programs
        if bool(program)
    ]
    logger.info(
        f'Found {len(valid_programs)} valid locations '
        f'from {len(unique_programs)} unique locations.'
    )

    NUM_LOCATIONS = 8
    logger.info(
        f'Processing {min(len(valid_programs), NUM_LOCATIONS)} '
        'valid locations.'
    )
    for input_program in valid_programs[:NUM_LOCATIONS]:
        logger.info(f'Attempting to patch {input_program}.')

        processed_source = input_program.processed_source
        program_id = input_program.program_id
        line_number = input_program.line_number

        if not quiet:
            logger.info('Quiet mode disabled. Writing source files to disk.')
            # Write original and processed source
            original_source_path = (
                Path(source_dir) / f'{program_id}.original_source'
            )
            MetadataUtils.write_file(
                text=input_program.original_source,
                path=original_source_path
            )
            processed_source_path = (
                Path(source_dir) / f'{program_id}.processed_source'
            )
            MetadataUtils.write_file(
                text=processed_source,
                path=processed_source_path
            )

        cost = {}
        # Get descriptions
        describer = CWEDescriber(
            input_program=input_program,
            description_prompt_dir=description_prompt_dir,
            description_dir=description_dir,
            description_models=DESCRIPTION_MODELS,
            quiet=quiet
        )
        descriptions, cost = describer.get_descriptions(cost=cost)

        # Get patch
        neighbors = searcher.search(
            source=processed_source, cwe_id=cwe_id, count=NUM_NEIGHBORS)
        fixer = Fixer(
            input_program=input_program,
            neighbors=neighbors,
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
                    input_program=input_program,
                    describer_id=patch['describer_id'],
                    description=patch['description'],
                    fixer_id=patch['fixer_id'],
                    patch_lines=patch['patch'].lines,
                    patch_path=str(patch['patch_path']),
                    reviewer_id=''
                )
            )
        reviewer = Reviewer(
            input_program=input_program,
            review_models=REVIEW_MODELS,
            review_prompt_dir=review_prompt_dir,
            review_dir=review_dir,
            patch_dir=patch_dir,
            output_dir=output_dir,
            quiet=quiet
        )
        reviewed_patches = reviewer.get_reviews(patches=patches, cost=cost)
        for patch in reviewed_patches:
            all_patches.append(
                MetadataUtils.process_patch(
                    input_program=input_program,
                    describer_id=patch['describer_id'],
                    description=patch['description'],
                    fixer_id=patch['fixer_id'],
                    patch_lines=patch['patch'].lines,
                    patch_path=str(patch['patch_path']),
                    reviewer_id=patch['reviewer_id']
                )
            )

    metadata_path = Path(output_dir) / 'generated_patches.json'
    metadata = {
        'language': language,
        'cwe_id': cwe_id,
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

    #   [bool]: Should we use the test config?
    use_test = args.use_test

    #   [bool]: Should we suppress writing prompts and raw responses?
    quiet = args.quiet

    logger.info(
        f'Attempting to run using (input_path={input_path}, '
        f'use_test={use_test}, quiet={quiet}).'
    )
    try:
        metadata = run(input_path=input_path, use_test=use_test, quiet=quiet)
        logger.info(
            'Multi-location mode produced '
            f'{len(metadata.get("patches", []))} patches.'
        )
    except Exception as e:
        logger.error(f'Running the tool produced {e}.')
