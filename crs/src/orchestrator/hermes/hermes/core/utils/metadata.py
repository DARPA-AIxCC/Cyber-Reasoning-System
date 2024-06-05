from hermes.log import logger
from hermes.config.config import WRITE_TEMP

from pathlib import Path
import tempfile
import json


class StringCastJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            logger.warning(f'Cannot automatically serialize {type(obj)}. '
                         'Casting to string instead.')
            return str(obj)


class MetadataUtils:
    @staticmethod
    def process_patch(
        input_program,
        describer_id,
        fixer_id,
        description,
        patch_lines,
        patch_path,
        reviewer_id=None
    ):
        source_path = input_program.file_path
        line_number = input_program.line_number

        return {
            # Buggy program metadata
            'source_path': str(source_path.name),
            'line_number': line_number,
            # Patch data
            'patch_file': Path(patch_path).name,
            'patch_content': patch_lines,
            # Patch metadata
            'describer_id': describer_id,
            'description': description,
            'fixer_id': fixer_id,
            'reviewer_id': reviewer_id,
        }
    @staticmethod
    def _patch_type_mapping():
        return {
            'invalid': 'There seems to be a syntax error in the patch.',
            'incorrect': 'The patch does not fix the vulnerability.',
            'failure-fixing': (
                'The patch fixes the vulnerability, '
                'but it introduces another bug.'
            )
        }

    @staticmethod
    def get_supported_patch_types():
        return list(MetadataUtils._patch_type_mapping().keys())

    @staticmethod
    def process_patch_type(patch_type):
        if not isinstance(patch_type, str):
            raise TypeError(f'Expected string. Got {type(patch_type)} instead.')

        patch_type = patch_type.lower()
        type_mapping = MetadataUtils._patch_type_mapping()

        if patch_type not in type_mapping.keys():
            raise ValueError(
                f'{patch_type} not supported. '
                f'Try {list(type_mapping.keys())}'
            )
        return type_mapping[patch_type]

    @staticmethod
    def process_locations(first, second, total=10):
        unique_first = list(set(first))
        unique_second = list(set(second))
        print(unique_first, unique_second)

    @staticmethod
    def write_file(text: str, path: Path, header: str = None):
        """Write a file given its content and path.
        -   If the user attempts to write content that isn't a string,
        a warning will be sent to the logger before attempting to
        convert [text] to a string.
        -   If the user attempts to write an empty file, nothing will be written.

        Parameters
        ----------
        text : [str]
            Content of the file.
        path : [pathlib.Path]
            Path of the file to be written.
        header : str, optional
            Optional header to be written before the content, by default None
        """
        if not isinstance(text, str):
            logger.warning(
                f'Attempting to write {type(text)}. Casting to string.'
            )
        if not text:
            logger.warning(
                f'Attempting to write an empty file at: {path}. Skipping.'
            )
            return

        path = Path(path)
        try:
            with path.open("w") as file:
                if header:
                    file.write('\n####################\n')
                    file.write(str(header))
                    file.write('\n####################\n')
                file.write(str(text))
            logger.info(f"Successfully wrote {path}.")
        except Exception as e:
            logger.error(f"An error occurred while writing the file: {e}")

    @staticmethod
    def dump_dict(data, path):
        if not isinstance(data, dict):
            raise TypeError(f'Expected dict. Got {type(data)} instead.')
        path = Path(path)
        try:
            with open(path, 'w') as file:
                json.dump(data, file, indent=4, cls=StringCastJSONEncoder)
            logger.info(f'Successfully wrote {path}.')
        except Exception as e:
            logger.warning(f'Failed to dump dict. Got {e}.')

    def setup_directories(output_dir, base_dir=None):
        """Setup directories required to store outputs, prompts, and processed
        patches.

        Parameters
        ----------
        output_dir : [pathlib.Path]
            Directory to store all outputs in.
        base_dir : [pathlib.Path]
            Base directory to use to store all outputs, read all files, etc...

        Returns
        -------
        [dict[[str]: [pathlib.Path]]]
            A dict whose keys are strings and values are pathlib.Path objects
            that represent the directories.
        """
        if not base_dir:
            base_dir = Path.cwd()
        base_dir = Path(base_dir)

        output_dir = base_dir / Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        patch_dir = Path(output_dir, "patches")
        patch_dir.mkdir(parents=True, exist_ok=True)

        original_output_dir = output_dir
        directory_info_file = Path(output_dir) / 'directories.json'

        if WRITE_TEMP:
            temp_dir = Path(tempfile.mkdtemp())
            logger.info(f'Using {temp_dir} to store intermediate outputs.')
            output_dir = temp_dir

        # Directory to store input source code before and after processing
        source_dir = Path(output_dir) / 'source'
        source_dir.mkdir(parents=True, exist_ok=True)

        # Base directory for all prompts
        prompt_dir = Path(output_dir) / 'prompts'
        prompt_dir.mkdir(parents=True, exist_ok=True)
        # Directory to store description prompts
        description_prompt_dir = Path(prompt_dir) / 'description'
        description_prompt_dir.mkdir(parents=True, exist_ok=True)
        # Directory to store repair prompts
        repair_prompt_dir = Path(prompt_dir) / 'repair'
        repair_prompt_dir.mkdir(parents=True, exist_ok=True)
        # Directory to store review prompts
        review_prompt_dir = Path(prompt_dir) / 'review'
        review_prompt_dir.mkdir(parents=True, exist_ok=True)
        # Directory to store description outputs
        description_dir = Path(output_dir) / 'description'
        description_dir.mkdir(parents=True, exist_ok=True)
        # Directory to store repair outputs
        raw_patch_dir = Path(output_dir, "raw_patches")
        raw_patch_dir.mkdir(parents=True, exist_ok=True)
        # Directory to store review outputs
        review_dir = Path(output_dir, "review")
        review_dir.mkdir(parents=True, exist_ok=True)

        directories = {
            'original_output_dir': original_output_dir,
            'output_dir': output_dir,
            'source_dir': source_dir,
            'prompt_dir': prompt_dir,
            'description_prompt_dir': description_prompt_dir,
            'repair_prompt_dir': repair_prompt_dir,
            'review_prompt_dir': review_prompt_dir,
            'description_dir': description_dir,
            'patch_dir': patch_dir,
            'raw_patch_dir': raw_patch_dir,
            'review_dir': review_dir
        }
        logger.info('Finished creating directories.')
        MetadataUtils.dump_dict(data=directories,path=directory_info_file)
        return directories