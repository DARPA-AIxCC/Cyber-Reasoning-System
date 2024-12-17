from pathlib import Path
from typing import List


class Program:
    def __init__(
            self,
            original_source: str,
            file_path: Path,
            cwe_id: str,
            line_number: int,
            processed_lines: List[str] = '',
            processed_source: str = '',
            program_id: str = ''
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

        self.file_path: Path = Path(file_path)
        self.file_name: str = self.file_path.stem

        self.cwe_id: str = cwe_id
        if processed_lines:
            self.processed_lines: List[str] = processed_lines
            self.processed_source: str = '\n'.join(self.processed_lines)
        else:
            self.processed_source = processed_source
            self.processed_lines = processed_source.splitlines()
        self.line_number: int = line_number
        if program_id:
            self.program_id = program_id
        else:
            self.program_id = self.file_name

    def __eq__(self, other):
        """Check if two programs are equal.
        Program A is equal to Program B iff:
            -   They have the same file path
            -   They have the same source code
                (sanity check for previous condition)
            -   They have the same CWE-ID
            -   They have the same code after the preprocessor runs.
                This step basically checks if the extracted function is
                the same.
        Parameters
        ----------
        other : [Program]
            Program to compare with

        Returns
        -------
        [bool]
            True iff the programs are equal. False otherwise.
        """
        if not isinstance(other, Program):
            return False
        if self.file_path != other.file_path:
            return False
        if self.original_source != other.original_source:
            return False
        if self.cwe_id != other.cwe_id:
            return False
        if self.processed_source != other.processed_source:
            return False
        return True

    def __repr__(self) -> str:
        if self:
            return (
                f'Program(CWE-ID={self.cwe_id}, '
                f'path={self.file_path}, line={self.line_number})'
            )
        else:
            return (f'EmptyProgram(path={self.file_path})')

    def __hash__(self):
        """Return a hash value for the program."""
        return hash(
            (
                self.file_path,
                self.original_source,
                self.cwe_id,
                self.processed_source
            )
        )

    def __bool__(self):
        """Check if a Progfam object is valid.
        A valid Program must have a cwe_id, line_number, and original_source.

        Returns
        -------
        [bool]
            If the program is valid, return True. False otherwise.
        """
        if (
            self.cwe_id and
            self.line_number and
            self.original_source
        ):
            return True
        return False
