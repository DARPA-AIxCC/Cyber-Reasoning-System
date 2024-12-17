from typing import List
import difflib
from pathlib import Path

from hermes.core.program import Program
from hermes.core.response import Response

from hermes.core.utils.metadata import MetadataUtils
from hermes.log import logger


class Patch:
    def __init__(self, response: Response):
        """Object that represents a patch.
        In essence, this is object is the result of attempting to extract
        a patch from a model's response.
        Contains all relevant meta-data, in addition to generate_diff().

        Parameters
        ----------
        response: [Response]
            A Response object that contains a model's raw response.
        """
        self.response: Response = response
        self.source_program: Program = self.response.source_program

        # Meta-data
        self.source: str = self.source_program.processed_source
        self.source_path: Path = self.source_program.file_path
        self.line_number: int = self.source_program.line_number
        self.file_name: str = self.source_program.file_name

        self.model_id: int = self.response.model_id

        # Patch content
        self.lines: List[str] = self.response.get_code()
        self.content = ''.join(self.lines)
        self.diff = self.generate_diff()

    def __repr__(self) -> str:
        return f"Patch(lines={self.lines}, line_number={self.line_number})"

    def __eq__(self, other):
        if self.source_program != other.source_program:
            return False
        if self.diff != other.diff:
            return False
        return True

    def generate_diff(self):
        """Generate diff representing the Patch object.

        Returns
        -------
        [str]
            String with the diff contents.
        """
        source_lines = self.source.splitlines()
        patch_lines = self.lines

        offset_lines = ["\n"] * self.line_number
        source_lines = offset_lines + source_lines
        patch_lines = offset_lines + patch_lines

        diff = difflib.unified_diff(
            source_lines,
            patch_lines,
            n=0,
            lineterm="",
            tofile=str(self.source_path),
            fromfile=str(self.source_path),
        )
        diff_text = "\n".join(list(diff)) + "\n"
        if not diff_text:
            logger.warning('Generated patch does not change anything.')
        return diff_text

    def write(self, path: Path):
        if self.content:
            MetadataUtils.write_file(text=self.generate_diff(), path=path)
        else:
            logger.warning('Patch is empty. Skipping.')
