package tss.aicc;

import java.util.Map;
import java.util.Set;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.io.IOException;

import java.util.ArrayList;
import java.nio.file.Paths;
import java.nio.file.Files;
import java.util.stream.Collectors;

import spoon.Launcher;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtConstructor;
import spoon.reflect.code.CtConstructorCall;
import spoon.reflect.CtModel;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.code.CtInvocation;
import spoon.reflect.cu.SourcePosition;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.reference.CtExecutableReference;
import spoon.reflect.visitor.filter.TypeFilter;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import picocli.CommandLine.Option;
import picocli.CommandLine.Parameters;
import picocli.CommandLine;

// import java.lang.reflect.Constructor;
// import java.lang.reflect.Method;
import java.util.List;

class Pair<K, V> {
    private final K key;
    private final V value;

    public Pair(K key, V value) {
        this.key = key;
        this.value = value;
    }

    public K getKey() {
        return key;
    }

    public V getValue() {
        return value;
    }

    @Override
    public String toString() {
        return "Pair{" +
                "key=" + key +
                ", value=" + value +
                '}';
    }
}

class Node implements Comparable<Node> {
    private String qualifiedClassName;
    private String methodName;
    private String[] argTypes;
    private String[] argNames;

    public Node(String qualifiedClassName, String methodName, String[] argTypes, String[] argNames) {
        this.qualifiedClassName = qualifiedClassName;
        this.methodName = methodName;
        this.argTypes = argTypes;
        this.argNames = argNames;
    }
    public int printNode() {
//    	System.out.println("qualifiedClassName: " + this.qualifiedClassName);
//	System.out.print("methodName: " + this.methodName);
	//System.out.println("argTypes: " + this.argTypes);
	//System.out.print("length of argTypes " + this.argTypes.length);
	final int prime = 31;
        int result = 1;
        result = prime * result + ((qualifiedClassName == null) ? 0 : this.qualifiedClassName.hashCode());
	System.out.println("\nresult:  for " + this.qualifiedClassName+ "  " +  result);

	System.out.println("\nHash the raw string  for " + this.qualifiedClassName + "   is  "  +  this.qualifiedClassName.hashCode());
        //result = prime * result + ((this.methodName == null) ? 0 : this.methodName.hashCode());
	//System.out.println("result for  " + this.methodName + result);
        //result = prime * result + this.argTypes.length;
	//System.out.println("result for args : " + result);

        return result;
    }

    public static Node fromCtMethod(CtMethod<?> method) {
        String qualifiedClassName = method.getDeclaringType().getQualifiedName();
        String methodName = method.getSimpleName();
        String[] argTypes = method.getParameters().stream().map(p -> p.getType().getQualifiedName())
                .toArray(String[]::new);
        String[] argNames = method.getParameters().stream().map(p -> p.getReference().getSimpleName())
                .toArray(String[]::new);
        return new Node(qualifiedClassName, methodName, argTypes, argNames);
    }

    public static Node fromCtConstructor(CtConstructor<?> constructor) {
        String qualifiedClassName = constructor.getDeclaringType().getQualifiedName();
        String methodName = "<init>";
        String[] argTypes = constructor.getParameters().stream().map(p -> p.getType().getQualifiedName())
                .toArray(String[]::new);
        String[] argNames = constructor.getParameters().stream().map(p -> p.getReference().getSimpleName())
                .toArray(String[]::new);
        return new Node(qualifiedClassName, methodName, argTypes, argNames);
    }

    public static Node fromCtConstructorCall(CtConstructorCall<?> constructorCall) {
        CtExecutableReference<?> executable = constructorCall.getExecutable();
        return fromCtExecutableReference(executable);
    }

    public static Node fromCtExecutableReference(CtExecutableReference<?> executable) {
        String qualifiedClassName = null;
        try {
            qualifiedClassName = executable.getDeclaringType().getQualifiedName();
        } catch (NullPointerException e) {
            qualifiedClassName = "<UNKNOWN>";
            System.err.println(
                    "WARNING: Could not determine declaring type for " + executable + ". Setting to <UNKNOWN>.");
        }

        String methodName = executable.getSimpleName();

        String[] argTypes = null;
        try {
            argTypes = executable.getParameters().stream().map(p -> p.getTypeDeclaration().getQualifiedName())
                    .toArray(String[]::new);
        } catch (NullPointerException e) {
            System.err
                    .println("WARNING: Could not determine argument types for " + qualifiedClassName + "::" + methodName
                            + ". Setting to <UNKNOWN>.");
            argTypes = new String[] { "<UNKNOWN>" };
        }

        String[] argNames = null;
        try {
            argNames = executable.getDeclaration().getParameters().stream().map(p -> p.getSimpleName())
                    .toArray(String[]::new);
        } catch (NullPointerException e) {
            System.err
                    .println("WARNING: Could not determine argument names for " + qualifiedClassName + "::" + methodName
                            + ". Setting to <UNKNOWN>.");
            argNames = new String[] { "<UNKNOWN>" };
        }

        return new Node(qualifiedClassName, methodName, argTypes, argNames);
    }
    // public Node(Constructor<?> constructor) {
    // this.qualifiedClassName = constructor.getDeclaringClass().getCanonicalName();
    // this.methodName = "<init>";
    // this.argTypes = Arrays.asList(constructor.getParameters()).stream().map(p ->
    // p.getType().getCanonicalName())
    // .toArray(String[]::new);
    // }

    // public Node(Method method) {
    // this.qualifiedClassName = method.getDeclaringClass().getCanonicalName();
    // this.methodName = method.getName();
    // this.argTypes = Arrays.asList(method.getParameters()).stream().map(p ->
    // p.getType().getCanonicalName())
    // .toArray(String[]::new);
    // }

    @Override
    public int hashCode() {
        final int prime = 31;
        int result = 1;
        result = prime * result + ((qualifiedClassName == null) ? 0 : qualifiedClassName.hashCode());
        result = prime * result + ((methodName == null) ? 0 : methodName.hashCode());
        result = prime * result + argTypes.length;
        //result = prime * result + argNames.length;
        return result;
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj)
            return true;
        if (obj == null)
            return false;
        if (getClass() != obj.getClass())
            return false;
        Node other = (Node) obj;
        if (qualifiedClassName == null) {
            if (other.qualifiedClassName != null)
                return false;
        } else if (!qualifiedClassName.equals(other.qualifiedClassName))
            return false;
        if (methodName == null) {
            if (other.methodName != null)
                return false;
        } else if (!methodName.equals(other.methodName))
            return false;
	//if (argTypes.length != other.argTypes.length)
	//  return false;
        if (!Arrays.equals(argTypes, other.argTypes))
            return false;
        return true;
    }

    @Override
    public String toString() {
        return qualifiedClassName + "::" + methodName + "(" + String.join(", ", argTypes) + ")";
    }

    @Override
    public int compareTo(Node o) {
        return this.toString().compareTo(o.toString());
    }

}

class Position {
    // Use the same format as treesitter
    // 1. The line, column, and offsets are 0-based
    // 2. Line is inclusive on both ends
    // 3. Column and offsets are left-inclusive, right-exclusive

    private int line;
    private int endLine;
    private int column;
    private int endColumn;
    private int start;
    private int end;
    private String file;

    public static Position fromSourcePosition(SourcePosition sourcePos) {
        Position pos = new Position();

        // getLine(), getEndLn(), getColumn(), getEndColumn() are 1-based and inclusive
        // on both ends
        // getSourceStart(), getSourceEnd() are 0-based and inclusive on both ends
        pos.line = sourcePos.getLine() - 1;
        pos.endLine = sourcePos.getEndLine() - 1;
        pos.column = sourcePos.getColumn() - 1;
        pos.endColumn = sourcePos.getEndColumn();
        pos.start = sourcePos.getSourceStart();
        pos.end = sourcePos.getSourceEnd() + 1;
        pos.file = sourcePos.getFile().getAbsolutePath();

        return pos;
    }
}

class Edge {
    private String caller;
    private String callee;
    private Position position;

    public Edge(String caller, String callee, Position position) {
        this.caller = caller;
        this.callee = callee;
        this.position = position;
    }
}

class HookTarget {
    private Node node;
    private Position position;
    private String hookName;

    public HookTarget(Node node, Position position, String hookName) {
        this.node = node;
        this.position = position;
        this.hookName = hookName;
    }
}

class CallGraph {
    private Map<String, Node> nodes;
    private List<Edge> edges;
    private List<HookTarget> hookTargets;

    public CallGraph(Map<String, Node> nodes, List<Edge> edges) {
        this.nodes = nodes;
        this.edges = edges;
        this.hookTargets = new ArrayList<>();
    }

    public void addHookTarget(HookTarget hookTarget) {
        hookTargets.add(hookTarget);
    }
}

class Options {
    @Parameters(paramLabel = "FILE", description = "one or more files to parse")
    String[] files;

    @Option(names = { "-l",
            "--list-file" }, description = "file that lists source files to be parsed, one per line", defaultValue = "")
    String listFile;

    @Option(names = { "-o", "--output-file" }, description = "output file")
    String outFile;

    @Option(names = { "-h", "--help" }, usageHelp = true, description = "display this help message")
    boolean usageHelpRequested;

    @Option(names = { "-V", "--version" }, versionHelp = true, description = "display version info")
    boolean versionInfoRequested;
    @Option(names = { "-s", "--sanitizers" }, description = "Sanitizer type")
    String sanitizerTypes;
}

public class CallGraphGenerator {
    //static Map<Node, String> hooks = new HashMap<>();
    static List<Pair<Node, String>>  hooks = new ArrayList<>();
    static Map<Node, String> specifiedHooks = new HashMap<>();

    public static Pair<Node, String> makePair(Node node, String hookName) {
	return new Pair<Node, String>(node, hookName);
    }

    static {
	    // for OS command injection
        hooks.add(makePair(new Node("java.lang.ProcessBuilder", "start", new String[] {}, new String[] {}),
                "OsCommandInjection"));
        hooks.add( makePair(new Node("java.lang.ProcessImpl", "start", new String[] {}, new String[] {}),
                "OsCommandInjection"));

	// FileReadWrite  
	// for file system traversal
	// java.io.FileReader
        hooks.add(makePair(new Node("java.io.FileReader", "<init>", new String[] {"java.lang.String"}, new String[] {"fileName"}),
                "FileSystemTraversal"));
        hooks.add(makePair(new Node("java.io.FileReader", "<init>", new String[] {"java.io.FileDescriptor"}, new String[] {"fd"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.io.FileReader", "<init>", new String[] {"java.io.File"}, new String[] {"path"}),
                "FileSystemTraversal"));

        hooks.add( makePair(new Node("java.io.FileWriter", "<init>", new String[] {"java.io.File"}, new String[] {"file"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.io.FileWriter", "<init>", new String[] {"java.io.File", "java.lang.boolean"}, new String[] {"file", "append"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.io.FileWriter", "<init>", new String[] {"java.io.FileDescriptor"}, new String[] {"fd"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.io.FileWriter", "<init>", new String[] {"java.io.String"}, new String[] {"fileName"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.io.FileWriter", "<init>", new String[] {"java.lang.String", "java.lang.boolean"}, new String[] {"fileName", "append"}),
                "FileSystemTraversal"));

        hooks.add( makePair(new Node("java.io.FileInputStream", "<init>", new String[] {"java.io.File"}, new String[] {"file"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.io.FileInputStream", "<init>", new String[] {"java.io.FileDescriptor"}, new String[] {"fdObj"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.io.FileInputStream", "<init>", new String[] {"java.lang.String"}, new String[] {"name"}),
                "FileSystemTraversal"));

        hooks.add( makePair(new Node("java.io.FileOutputStream", "<init>", new String[] {"java.io.File"}, new String[] {"file"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.io.FileOutputStream", "<init>", new String[] {"java.io.File", "java.lang.boolean"}, new String[] {"path", "append"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.io.FileOutputStream", "<init>", new String[] {"java.io.FileDescriptor"}, new String[] {"fdObj"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.io.FileOutputStream", "<init>", new String[] {"java.lang.String"}, new String[] {"name"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.io.FileOutputStream", "<init>", new String[] {"java.lang.String", "java.lang.boolean"}, new String[] {"path", "append"}),
                "FileSystemTraversal"));

        hooks.add( makePair(new Node("java.util.Scanner", "<init>", new String[] {"java.io.File"}, new String[] {"source"}),
                "FileSystemTraversal"));

	// java.nio.file.File 
	/*
	 *static SeekableByteChannel	newByteChannel(Path path, OpenOption... options)
	Opens or creates a file, returning a seekable byte channel to access the file.
	static SeekableByteChannel	newByteChannel(Path path, Set<? extends OpenOption> options, FileAttribute<?>... attrs)k
	 */
        hooks.add(makePair(new Node("java.nio.file.File", "newByteChannel", new String[] {"java.nio.file.Path", "java.nio.file.OpenOption"}, new String[] {"path", "options"}),
                "FileSystemTraversal"));
        hooks.add(makePair(new Node("java.nio.file.File", "newByteChannel", new String[] {"java.nio.file.Path", "java.util.Set", "java.nio.file.attribute.FileAttribute"}, new String[] {"path", "options", "attrs"}),
                "FileSystemTraversal"));

        hooks.add(makePair(new Node("java.nio.file.File", "newBufferedReader", new String[] {"java.nio.file.Path"}, new String[] {"path"}),
                "FileSystemTraversal"));
        hooks.add(makePair(new Node("java.nio.file.File", "newBufferedReader", new String[] {"java.nio.file.Path", "java.nio.charset.Charset"}, new String[] {"path", "cs"}),
                "FileSystemTraversal"));

        hooks.add( makePair(new Node("java.nio.file.File", "newBufferedWriter", new String[] {"java.nio.file.Path", "java.nio.charset.Charset", "java.nio.file.OpenOption"}, new String[] {"path", "cs", "options"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.nio.file.File", "newBufferedWriter", new String[] {"java.nio.file.Path", "java.nio.file.OpenOption"}, new String[] {"path", "options"}),
                "FileSystemTraversal"));

        //hooks.add( makePair(new Node("java.nio.file.File", "readString", new String[] {"java.io.File"}, new String[] {"path"}),

        //        "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.nio.file.File", "readAllBytes", new String[] {"java.nio.file.Path"}, new String[] {"path"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.nio.file.File", "readAllLines", new String[] {"java.nio.file.Path"}, new String[] {"path"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.nio.file.File", "readSymbolicLink", new String[] {"java.nio.file.Path"}, new String[] {"link"}),
                "FileSystemTraversal"));

        hooks.add( makePair(new Node("java.nio.file.File", "write", new String[] {"java.io.file.Path", "java.lang.byte[]", "java.nio.file.OpenOption"}, new String[] {"path", "bytes", "options"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.nio.file.File", "write", new String[] {"java.io.file.Path", "java.lang.CharSequence", "java.nio.charset.Charset", "java.nio.file.OpenOption"}, new String[] {"path", "lines", "cs",  "options"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.nio.file.File", "write", new String[] {"java.io.file.Path", "java.lang.CharSequence", "java.nio.file.OpenOption"}, new String[] {"path", "lines",  "options"}),
                "FileSystemTraversal"));
        //hooks.add( makePair(new Node("java.nio.file.File", "writeString", new String[] {"java.io.File"}, new String[] {"path"}),
         //       "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.nio.file.File", "newInputStream", new String[] {"java.nio.file.Path", "java.nio.file.OpenOption"}, new String[] {"path", "options"}),
                "FileSystemTraversal"));
        hooks.add( makePair(new Node("java.nio.file.File", "newOutputStream", new String[] {"java.io.file.Path", "java.nio.file.OpenOption"}, new String[] {"path", "options"}),
                "FileSystemTraversal"));

        hooks.add(makePair(new Node("java.nio.channels.FileChannel", "open", new String[] {"java.nio.file.Path", "java.nio.file.OpenOption"}, new String[] {"path", "options"}),
                "FileSystemTraversal"));
        hooks.add(makePair(new Node("java.nio.channels.FileChannel", "open", new String[] {"java.nio.file.Path", "java.util.Set", "java.nio.file.FileAttribute"}, new String[] {"path", "options", "attrs"}),
                "FileSystemTraversal"));

	// For refelctive calls
        hooks.add(makePair(new Node("java.lang.Class", "forName", new String[] {"java.lang.String"}, new String[] {"className"}),
                "ReflectiveCall"));
        hooks.add( makePair(new Node("java.lang.Class", "forName", new String[] {"java.lang.String", "java.lang.Boolean", "java.lang.ClassLoader"}, new String[] {"className", "initialize", "loader"}),
                "ReflectiveCall"));
        hooks.add(makePair( new Node("java.lang.System", "load", new String[] {"java.lang.String"}, new String[] {"filename"}),
                "ReflectiveCall"));
        hooks.add(makePair(new Node("java.lang.System", "loadLibrary", new String[] {"java.lang.String"}, new String[] {"libname"}),
              "ReflectiveCall"));
        hooks.add(makePair(new Node("java.lang.System", "mapLibraryName", new String[] {"java.lang.String"}, new String[] {"libname"}),
                "ReflectiveCall"));
        hooks.add( makePair(new Node("java.lang.Runtime", "load", new String[] {"java.lang.String"}, new String[] {"filename"}),
                "ReflectiveCall"));
        hooks.add(makePair(new Node("java.lang.Runtime", "loadLibrary", new String[] {"java.lang.String"}, new String[] {"filename"}),
                "ReflectiveCall"));

	// for Severside Side Request Forgery
        hooks.add(makePair( new Node("java.net.SocketImpl", "connect", new String[] {"java.net.SocketAddress"}, new String[] {"endpoint"}),
                "ServerSideRequestForgery"));
        hooks.add(makePair( new Node("java.net.Socket", "connect", new String[] {"java.net.SocketAddress"}, new String[] {"endpoint"}),
                "ServerSideRequestForgery"));
        hooks.add(makePair( new Node("java.net.SocksSocketImpl", "connect", new String[] {"java.net.SocketAddress"}, new String[] {"endpoint"}),
                "ServerSideRequestForgery"));

	// FOR LDA injection
        hooks.add(makePair(new Node("javax.naming.directory.DirContext", "search", new String[] {"javax.naming.Name", "javax.naming.directory.Attributes"}, new String[] {"name", "matchingAttributes"}),
                "LdapInjection"));

        hooks.add(makePair(new Node("javax.naming.directory.DirContext", "search", new String[] {"javax.naming.Name", "javax.naming.directory.Attributes", "java.lang.String[]"}, new String[] {"name", "matchingAttributes", "attributesToReturn"}),
                "LdapInjection"));

        hooks.add(makePair(new Node("javax.naming.directory.DirContext", "search", new String[] {"javax.naming.Name", "java.lang.String", "java.lang.Object[]", "javax.naming.directory.SearchControls"}, new String[] {"name", "filterExpr", "filterArgs", "cons"}),
                "LdapInjection"));

	// search(Name name, String filter, SearchControls cons)
        hooks.add(makePair(new Node("javax.naming.directory.DirContext", "search", new String[] {"javax.naming.Name", "java.lang.String", "javax.naming.directory.SearchControls"}, new String[] {"name", "filte", "cons"}),
                "LdapInjection"));
	//search(String name, Attributes matchingAttributes)
        hooks.add(makePair(new Node("javax.naming.directory.DirContext", "search", new String[] {"java.lang.String", "javax.naming.directory.Attributes"}, new String[] {"name", "matchingAttributes"}),
                "LdapInjection"));
	// 	search(String name, Attributes matchingAttributes, String[] attributesToReturn)
        hooks.add(makePair(new Node("javax.naming.directory.DirContext", "search", new String[] {"java.lang.String", "javax.naming.directory.Attributes", "java.lang.String[]"}, new String[] {"name", "matchingAttributes", "attributesToReturn"}),
                "LdapInjection"));
	// search(String name, String filterExpr, Object[] filterArgs, SearchControls cons)
        hooks.add(makePair(new Node("javax.naming.directory.DirContext", "search", new String[] {"java.lang.String", "java.lang.String", "java.lang.Object[]", "javax.naming.directory.SearchControls"}, new String[] {"name", "filterExpr", "filterArgs", "cons"}),
                "LdapInjection"));
	//	search(String name, String filter, SearchControls cons)
        hooks.add(makePair(new Node("javax.naming.directory.DirContext", "search", new String[] {"java.lang.String", "java.lang.String", "javax.naming.directory.SearchControls"}, new String[] {"name", "filter", "cons"}),
                "LdapInjection"));
	
	// FOR NamingLookup
	// Object	lookup(Name name)
	// Object	lookup(String name)
        hooks.add(makePair(new Node("javax.naming.Context", "lookup", new String[] {"java.naming.Name"}, new String[] {"name"}),
                "NamingContextLookup"));
        hooks.add(makePair(new Node("javax.naming.Context", "lookup", new String[] {"java.lang.String"}, new String[] {"name"}),
                "NamingContextLookup"));
        // 	lookupLink(Name name)	
	// 	lookupLink(String name)
        hooks.add(makePair(new Node("javax.naming.Context", "lookupLink", new String[] {"java.naming.Name"}, new String[] {"name"}),
                "NamingContextLookup"));
        hooks.add(makePair(new Node("javax.naming.Context", "lookupLink", new String[] {"java.lang.String"}, new String[] {"name"}),
                "NamingContextLookup"));
	
	// object deserialization 
        hooks.add(makePair(new Node("java.io.ObjectInputStream", "<init>", new String[] {}, new String[] {}),
                "Deserialization"));
        hooks.add(makePair(new Node("java.io.ObjectInputStream", "<init>", new String[] {"java.io.InputStream"}, new String[] {"in"}),
                "Deserialization"));

        hooks.add(makePair(new Node("java.io.ObjectInputStream", "readObject", new String[] {}, new String[] {}),
                "Deserialization"));
        hooks.add(makePair(new Node("java.io.ObjectInputStream", "readObjectOverride", new String[] {}, new String[] {}),
                "Deserialization"));

        hooks.add(makePair(new Node("java.io.ObjectInputStream", "readUnshared", new String[] {}, new String[] {}),
                "Deserialization"));
	// ExpressionLanguageInjection
        hooks.add(makePair(new Node("javax.validation.ConstraintValidatorContext", "buildConstraintViolationWithTemplate", new String[] {"java.lang.String"}, new String[] {"messageTemplate"}), "ExpressionLanguageInjection"));

        hooks.add(makePair(new Node("javax.el.ExpressionFactory", "createValueExpression", new String[] {"jakarta.el.ELContext", "java.lang.String", "java.lang.Class<T>"}, new String[] {"context", "expression", "expectedType"}), 
	"ExpressionLanguageInjection"));
        hooks.add(makePair(new Node("javax.el.ExpressionFactory", "createValueExpression", new String[] {"java.lang.Object", "java.lang.Class<T>"}, new String[] {"instance", "expectedType"}), "ExpressionLanguageInjection"));
        hooks.add(makePair(new Node("javax.el.ExpressionFactory", "createMethodExpression", new String[] {"jakarta.el.ELContext", "java.lang.String", "java.lang.Class<T>", "java.lang.Class<?>[]"}, new String[] {"context", "expression", "expectedReturnType", "expectedParamTypes"}), "ExpressionLanguageInjection"));

        hooks.add(makePair(new Node("jakarta.el.ExpressionFactory", "createValueExpression", new String[] {"jakarta.el.ELContext", "java.lang.String", "java.lang.Class<T>"}, new String[] {"context", "expression", "expectedType"}), 
	"ExpressionLanguageInjection"));
        hooks.add(makePair(new Node("jakarta.el.ExpressionFactory", "createValueExpression", new String[] {"java.lang.Object", "java.lang.Class<T>"}, new String[] {"instance", "expectedType"}), "ExpressionLanguageInjection"));
        hooks.add(makePair(new Node("jakarta.el.ExpressionFactory", "createMethodExpression", new String[] {"jakarta.el.ELContext", "java.lang.String", "java.lang.Class<T>", "java.lang.Class<?>[]"}, new String[] {"context", "expression", "expectedReturnType", "expectedParamTypes"}), "ExpressionLanguageInjection"));

    }
    public static void main(java.lang.String[] args) throws IOException {
        Options options = new Options();
        CommandLine cmd = new CommandLine(options);
        cmd.parseArgs(args);
	List<String> inputSanitizerTypes = Arrays.asList(options.sanitizerTypes.split(","));

        if (cmd.isUsageHelpRequested()) {
            cmd.usage(cmd.getOut());
            return;
        } else if (cmd.isVersionHelpRequested()) {
            cmd.printVersionHelp(cmd.getOut());
            return;
        }
	for (Pair<Node, String> entry : hooks) {
		for(String sanitizerType : inputSanitizerTypes) {
			// the two sanitizers are implemented in the same way using same hooks.
			// Therefore, we do not additioanlly add the hooks for FileReadWrite
			if (sanitizerType.equals("FileReadWrite")) {
				sanitizerType = "FileSystemTraversal";
			}
			if (entry.getValue().equals(sanitizerType)) {
				specifiedHooks.put(entry.getKey(), entry.getValue());
			}
		}
	}
        String[] files = null;

        if (!options.listFile.isEmpty()) {
            files = Files.readAllLines(Paths.get(options.listFile)).toArray(new String[0]);
        } else if (options.files != null) {
            files = options.files;
        } else {
            System.err.println("No files specified. Exiting.");
            System.exit(1);
        }

        CallGraph graph = buildCallGraph(files);

        Gson gson = new GsonBuilder().setPrettyPrinting().create();
        String CallGraphString = gson.toJson(graph);

        if (options.outFile != null) {
            Files.write(Paths.get(options.outFile), CallGraphString.getBytes());
        } else {
            System.out.println(CallGraphString);

        }
    }

    public static List<String> qualifiedNames(String file) {
        // Initialize the Spoon Launcher
        Launcher launcher = new Launcher();
        launcher.getEnvironment().setIgnoreSyntaxErrors(true);
        // Add the input Java file to be parsed
        launcher.addInputResource(file);

        // Build the model
        launcher.buildModel();

        // Get the model
        CtModel model = launcher.getModel();

        return model.getAllTypes().stream().filter(x -> x instanceof CtClass).map(x -> x.getQualifiedName()).toList();

    }

    public static CallGraph buildCallGraph(String[] files) {
        List<Node> nodes = new ArrayList<>();

        Launcher launcher = new Launcher();

        Set<String> definedClasses = new HashSet<>();

        for (String file : files) {
            // System.err.printf("Filename is %s %n", file);
            try {
                List<String> qualifiedClassNames = qualifiedNames(file);
                if (qualifiedClassNames.stream().anyMatch(n -> definedClasses.contains(n))) {
                    continue;
                }
                qualifiedClassNames.forEach(definedClasses::add);
            } catch (Exception e) {
                System.err.printf("Failed is %s %n", file);
                continue;
            }

            launcher.addInputResource(file);

        }

        launcher.getEnvironment().setIgnoreSyntaxErrors(true);
        // Build Spoon model
        launcher.buildModel();
        CtModel model = launcher.getModel();

        // Iterate over all methods and constructors
        List<CtMethod<?>> methods = model.getElements(new TypeFilter<>(CtMethod.class));
        for (CtMethod<?> method : methods) {
	    int method_start_line = method.getPosition().getLine();
	    int method_end_line = method.getPosition().getEndLine();
            Node node = Node.fromCtMethod(method);
            nodes.add(node);

            List<CtInvocation<?>> methodCalls = method.getElements(new TypeFilter<>(CtInvocation.class));
            for (CtInvocation<?> methodCall : methodCalls) {
                CtExecutableReference<?> executable = methodCall.getExecutable();
                Node callee = Node.fromCtExecutableReference(executable);
                nodes.add(callee);
            }

            List<CtConstructorCall<?>> constructorCalls = method.getElements(new TypeFilter<>(CtConstructorCall.class));
            for (CtConstructorCall<?> constructorCall : constructorCalls) {
                Node callee = Node.fromCtConstructorCall(constructorCall);
                nodes.add(callee);
            }
        }

        List<CtConstructor<?>> constructors = model.getElements(new TypeFilter<>(CtConstructor.class));
        for (CtConstructor<?> constructor : constructors) {
            Node node = Node.fromCtConstructor(constructor);
            nodes.add(node);

            List<CtInvocation<?>> methodCalls = constructor.getElements(new TypeFilter<>(CtInvocation.class));
            for (CtInvocation<?> methodCall : methodCalls) {
                CtExecutableReference<?> executable = methodCall.getExecutable();
                Node callee = Node.fromCtExecutableReference(executable);
                nodes.add(callee);
            }

            List<CtConstructorCall<?>> constructorCalls = constructor
                    .getElements(new TypeFilter<>(CtConstructorCall.class));
            for (CtConstructorCall<?> constructorCall : constructorCalls) {
                Node callee = Node.fromCtConstructorCall(constructorCall);
                nodes.add(callee);
            }
        }

        nodes = nodes.stream().distinct().sorted().collect(Collectors.toList());

        Map<String, Node> nodesMap = new HashMap<>();
        Map<Node, String> reverseNodesMap = new HashMap<>();
        int nodeIndex = 0;
        for (Node node : nodes) {
            String index = nodeIndex + "";
            nodesMap.put(index, node);
            reverseNodesMap.put(node, index);

            nodeIndex++;
        }

        List<Edge> edges = new ArrayList<>();

        for (CtMethod<?> caller : methods) {
            String callerId = reverseNodesMap.get(Node.fromCtMethod(caller));

            // Extract method calls
            List<CtInvocation<?>> methodCalls = caller.getElements(new TypeFilter<>(CtInvocation.class));
            for (CtInvocation<?> methodCall : methodCalls) {
                CtExecutableReference<?> executable = methodCall.getExecutable();
                Node callee = Node.fromCtExecutableReference(executable);
                String calleeId = reverseNodesMap.get(callee);

                try {
                    Position position = Position.fromSourcePosition(methodCall.getPosition());
                    Edge edge = new Edge(callerId, calleeId, position);
                    edges.add(edge);
                } catch (Exception e) {
                    continue;
                }
            }

            List<CtConstructorCall<?>> constructorCalls = caller.getElements(new TypeFilter<>(CtConstructorCall.class));
            for (CtConstructorCall<?> constructorCall : constructorCalls) {
                Node callee = Node.fromCtConstructorCall(constructorCall);
                String calleeId = reverseNodesMap.get(callee);

                try {
                    Position position = Position.fromSourcePosition(constructorCall.getPosition());
                    Edge edge = new Edge(callerId, calleeId, position);
                    edges.add(edge);
                } catch (Exception e) {
                    continue;
                }
            }
        }

        List<HookTarget> hookTargets = new ArrayList<>();
        for (CtMethod<?> method : methods) {

            Map<String, List<Position>> hookPositions = findHookPositions(method);
            for (Map.Entry<String, List<Position>> entry : hookPositions.entrySet()) {
                String hookName = entry.getKey();
                List<Position> positions = entry.getValue();
                for (Position position : positions) {
                    Node node = Node.fromCtMethod(method);
                    HookTarget hookTarget = new HookTarget(node, position, hookName);
                    hookTargets.add(hookTarget);
                }
            }
        }

        CallGraph graph = new CallGraph(nodesMap, edges);
        hookTargets.forEach(graph::addHookTarget);

        return graph;
    }

    private static Map<String, List<Position>> findHookPositions(CtMethod<?> method) {
        Map<String, List<Position>> hookPositions = new HashMap<>();


        List<CtInvocation<?>> methodCalls = method.getElements(new TypeFilter<>(CtInvocation.class));
        for (CtInvocation<?> methodCall : methodCalls) {
            CtExecutableReference<?> executable = methodCall.getExecutable();
            Node callee = Node.fromCtExecutableReference(executable);

            if (specifiedHooks.containsKey(callee)) {
                String hookName = specifiedHooks.get(callee);
                List<Position> positions = hookPositions.getOrDefault(hookName, new ArrayList<>());
                try {
                    positions.add(Position.fromSourcePosition(methodCall.getPosition()));
                } catch (Exception e) {
                    continue;
                }
                hookPositions.put(hookName, positions);
            }
        }

        List<CtConstructorCall<?>> constructorCalls = method.getElements(new TypeFilter<>(CtConstructorCall.class));
        for (CtConstructorCall<?> constructorCall : constructorCalls) {
            Node callee = Node.fromCtConstructorCall(constructorCall);
	    String calleName = callee.toString();

            if (specifiedHooks.containsKey(callee)) {
                String hookName = specifiedHooks.get(callee);
                List<Position> positions = hookPositions.getOrDefault(hookName, new ArrayList<>());
                try {
                    positions.add(Position.fromSourcePosition(constructorCall.getPosition()));
                } catch (Exception e) {
                    continue;
                }
                hookPositions.put(hookName, positions);
            }
        }

        return hookPositions;
    }
}
