from typing import Dict, List, Optional
from tree_sitter import Language, Parser, Node

from pathlib import Path

import tree_sitter_python as tspython
import tree_sitter_cpp as tscpp
import tree_sitter_c as tsc
import tree_sitter_java as tsjava

from hermes.core.program import Program
from hermes.log import logger


class TreeSitter:
    def __init__(
            self,
            source: str,
            file_path: Path,
            cwe_id: str,
            language: str,
            program_id: str = ''
    ):
        self.source: str = source
        self.file_path = file_path
        self.cwe_id = cwe_id

        self.language: str = language.lower()
        if self.language not in self.supported_languages():
            raise ValueError(
                f'{self.language} is not in {self.supported_languages()}.'
        )

        self.parser: Parser = self.supported_parsers()[self.language]
        self.tree = self.parser.parse(
            bytes(self.source, 'utf-8')
        )
        self.program_id = program_id

    @staticmethod
    def supported_languages() -> List[str]:
        return list(TreeSitter.supported_parsers().keys())

    @staticmethod
    def supported_parsers() -> Dict[str, Parser]:
        return {
            "python": Parser(Language(tspython.language())),
            "cpp": Parser(Language(tscpp.language())),
            "c++": Parser(Language(tscpp.language())),
            "c": Parser(Language(tsc.language())),
            "java": Parser(Language(tsjava.language())),
        }

    def search_wrapper(self, line_number: int) -> Optional[Node]:
        candidates = self.get_context(line_number=line_number)
        function_node = [
            candidate for candidate in candidates
            if candidate.type in [
                'method_declaration',
                'function_definition',
                'function_declarator',
            ]
        ]

        if not function_node:
            logger.warning(
                f"Could not find function surrounding line {line_number}."
            )
            return candidates[0]
        return function_node[0]

    def get_context(self, line_number: int):
        candidates = []

        def traverse(n):
            if n.start_point.row <= line_number <= n.end_point.row:
                candidates.append(n)
            for child in n.children:
                traverse(child)

        traverse(self.tree.root_node)

        filtered_candidates = [
            candidate for candidate in candidates
            if (
                candidate.type in [
                    'block',
                    'method_declaration',
                    'function_definition',
                    'function_declarator',
                    'if_statement',
                    'case_statement',
                    'compound_statement',
                    'switch_statement',
                    'class_body',
                    'class_declaration'
                    ]
                )
            ]
        if not filtered_candidates:
            return candidates
        return filtered_candidates

    def get_lines(self, node: Node, line_numbers: bool) -> List[str]:
        lines = "".join(node.text.decode("utf-8")).split("\n")
        if line_numbers:
            lines = [
                f"{node.start_point.row + idx}: {line}"
                for idx, line in enumerate(lines)
            ]
        return Program(
            original_source=self.source,
            file_path=self.file_path,
            cwe_id=self.cwe_id,
            processed_lines=lines,
            line_number=int(node.start_point.row),
            program_id=self.program_id
        )


class Preprocessor:
    def __init__(self, file_path, cwe_id, language, program_id=''):
        logger.info(
            f'Attempting to preprocess path={file_path}, cwe_id={cwe_id}, '
            f'language={language}, program_id={program_id}.'
        )
        self.file_path = Path(file_path)
        self.source = ''
        if not self.file_path.is_file():
            logger.warning(f'{file_path} does not point to a file.')
        else:
            try:
                with open(self.file_path, 'r') as file:
                    self.source = file.read()
                logger.info(f'Successfully read {self.file_path}.')
            except Exception as e:
                logger.warning(
                    f'An error occurred while reading the file: {e}.'
                )

        self.cwe_id = cwe_id
        self.language = language
        self.program_id = program_id

    def process(self, line_number):
        """Process source code.
        Supports multiple options:
            -   If [line_numer] is None, returns unmodified source
            -   Otherwise:
                -   extracts the function inside which the line is located

        Parameters
        ----------
        line_number : [int]
            Number of the buggy line

        Returns
        -------
        [Program]
            -   Program object with the following attributes:
                -   source: the whole source code
                -   file_path: path of the file for the source code
                -   cwe_id: CWE ID of the vulnerability
                    -   if [line_number] is given:
                        -   candidates: list of candidates, where each
                            candidate is a trimmed-down version of the source
                    -   otherwise:
                        -   candidates: empty list

        Raises
        ------
        ValueError
            If requested line isn't inside a function, throw a ValueError
        """
        if self.source:
            try:
                helper = TreeSitter(
                    source=self.source,
                    file_path=self.file_path,
                    cwe_id=self.cwe_id,
                    language=self.language,
                    program_id=self.program_id
                )
                # Get node for the context
                result = helper.search_wrapper(line_number=line_number)

                if result:
                    return helper.get_lines(node=result, line_numbers=False)
                else:
                    raise ValueError(
                        f'Unable to find function for line {line_number}')
            except Exception as e:
                logger.warning(f'Preprocessor raised {e}.')
        logger.warning(
            f'Could not preprocess {self.file_path} at line {line_number}. '
            'Returning empty program.'
        )
        return Program(
            original_source=None,
            file_path=self.file_path,
            cwe_id=None,
            processed_lines=None,
            line_number=None,
        )
