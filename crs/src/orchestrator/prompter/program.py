from pathlib import Path
from typing import List


class Program:
    def __init__(
        self,
        original_source: str,
        file_path: Path,
        cwe_id: str,
        lines: List[str],
        line_number: int,
    ):
        """Object that represents a program.

        Parameters
        ----------
        original_source : [str]
            Contents of original source file.
        file_path : Path
            Path at which [source] is located.
            Required to generate the diff correctly.
        lines : List[str]
            Contents of the patch.
        line_number : int
            Real number for source content inside the source file.
            This is used because source can sometimes be processed to not start
            at the first line inside the file.
            Required to generate the diff correctly.
        """
        self.original_source: str = original_source

        self.file_path: Path = file_path
        self.file_name: str = self.file_path.stem

        self.cwe_id: str = cwe_id

        self.lines: List[str] = lines
        self.processed_source: str = "\n".join(self.lines)
        self.line_number: int = line_number

    def __repr__(self) -> str:
        return f"Program(CWE-ID={self.cwe_id}, line_number={self.line_number}, path={self.file_path})"
