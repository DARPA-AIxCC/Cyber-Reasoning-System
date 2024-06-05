import os

SENTINEL = {
    "OsCommandInjection": os.environ.get("JAZZER_COMMAND_INJECTION", "jazze"),
    "FileSystemTraversal": os.environ.get(
        "JAZZER_FILE_SYSTEM_TRAVERSAL_FILE_NAME", "jazzer-traversal"
    ),
    "ServerSideRequestForgery": os.environ.get("JAZZER_SSRF", "jazzer.example.com"),
    "FileReadWrite": os.environ.get("JAZZER_FILE_READ_WRITE", "jazzer"),
}

HOOKS = {
    "OsCommandInjection": {
        "conditions": [
            "Arrays.asList(new String[]{cmd}).contains('"
            + SENTINEL.get("OsCommandInjection")
            + "')"
        ]
    },
    "FileSystemTraversal": {
        "conditions": [
            "new String[]{path}).contains('"
            + SENTINEL.get("FileSystemTraversal")
            + "')"
        ]
    },
    "ServerSideRequestForgery": {
        "conditions": [
            "Arrays.asList(new String[]{url}).contains('"
            + SENTINEL.get("ServerSideRequestForgery")
            + "')"
        ]
    },
}


prompt_sanitizer_condition = {
    "OsCommandInjection": f"APIs like 'java.lang.ProcessBuilder' MUST contain a magic word named `{SENTINEL['OsCommandInjection']}` rather than the actual command",
    "FileSystemTraversal": f"File IO APIs such as java.nio.files MUST use any system path containing a magic word `{SENTINEL['FileSystemTraversal']}` rather than the actual path",
    "FileReadWrite": f"File IO APIs MUST use path containing a magic word called `{SENTINEL['FileReadWrite']}' rather than the actual path",
    "ServerSideRequestForgery": f"JAVA Socket APIs tries to communicate an URL which MUST contain a magic domain called {SENTINEL['ServerSideRequestForgery']} rather than the actual domain",
    "NamingContextLookup": f"APIs such as `Javax.naming.Context.lookup` and `Javax.naming.Context.lookupLink` are used with raw input without any sanitization. You MUST ensure name for the two APIs starting EITHER 'ldap://g.co/'  OR  'rmi://g.co/' because this is the pattern of the dangerous payload",
    "ReflectiveCall": f"APIs such as Class.forName('jaz.Zer').newInstance(). can be attacker-controlled class loading to load honeypot class via [Class.forName] or [ClassLoader.loadClass].",
    "LdapInjection": f"APIs such as `javax.naming.directory.InitialDirContext` has some dangerous input strings. This vulnerability is the exploitation of of Lightweight Directory Access Protocol",
    "Deserialization": f"Java deserialization vulnerabilities occur when a Java program deserializes untrusted data and is a massive application security issue. Some APIs such as `java.io.ObjectInputStream` can be exploited to create an instance `jaz.Zer` via reflection.",
    "ExpressionLanguageInjection": f"There are injectable inputs to an expression language interpreter which may lead to remote code execution. APIs such as `javax.el.ExpressionFactory`  or `javax.validation.ConstraintValidatorContext` can be exploited by attackers to execute arbitrary code.",
}


# prompt to tell required output
PROMPT_OUTPUT_REQ = """Note, this program takes a byte[] data as the input. Based on the above information, please possible input data[] that statisfies the conditions
\n\n
Your answer should be a python program that dumps the expected data to the file `input.bin`.
"""


def make_prompt_header(sanitizers: list[str]):
    PROMPT_HEADER = f"""You are a peneration testing engineer tasked with testing a Jenkins plugin applicaton. Now, we notice there is one or more possible vulnerabilities of {','.join(sanitizers)}."""
    PROMPT_HEADER += """Note we have VERY DIFFERENT definition of these type vulnerabilities. Here are the definitions:\n"""
    for sanitizer in sanitizers:
        PROMPT_HEADER += (
            f"\n* For {sanitizer}, {prompt_sanitizer_condition[sanitizer]}"
        )

    return PROMPT_HEADER

if __name__ == "__main__":
    print(make_prompt_header(["OsCommandInjection", "FileSystemTraversal", "ServerSideRequestForgery", "FileReadWrite"]))
    print(PROMPT_OUTPUT_REQ)
