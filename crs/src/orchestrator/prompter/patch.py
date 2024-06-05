from typing import List
import difflib
from pathlib import Path

from program import Program
from response import Response

from utils import logger


class Patch:
    def __init__(self, response: Response):
        """Object that represents a patch.
        Contains all relevant meta-data, in addition to generate_diff().

        Parameters
        ----------
        source_program : [Program]
            Buggy program that the patch attempts to fix.
        lines : List[str]
            Contents of the patch.
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

    def __repr__(self) -> str:
        return f"Patch(lines={self.lines}, line_number={self.line_number})"

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
        return diff_text

    def write(self, path: Path):
        try:
            with open(path, "w") as file:
                file.write(self.generate_diff())
            logger.info(f"Successfully wrote patch: {path}")
        except Exception as e:
            logger.warn(f"An error occurred while writing the file: {e}")
