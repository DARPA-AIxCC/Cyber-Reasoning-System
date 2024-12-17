import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

JAVA_LANGUAGE = Language(tsjava.language())

# Initialize the parser
parser = Parser()
parser.language = JAVA_LANGUAGE

# Define the query
query_string = """
[
  (character_literal)
  (string_literal)
] @string
(escape_sequence) @string.escape
"""


def collect_string_literals(src):
    token_lst = []
    tree = parser.parse(bytes(src, "utf8"))
    query = JAVA_LANGUAGE.query(query_string)
    captures = query.captures(tree.root_node)
    for capture in captures:
        node = capture[0]
        token = node.text.decode("utf8")
        token_lst.append(token)
    return token_lst
