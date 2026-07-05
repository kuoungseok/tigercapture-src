using System.Reflection.Emit;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;

static void Usage()
{
    Console.Error.WriteLine("Usage: MetadataDump <assembly.dll> [--match text] [--members] [--strings] [--il <type-or-method-substring>]");
}

if (args.Length == 0)
{
    Usage();
    return 2;
}

var assemblyPath = args[0];
var match = "";
var showMembers = false;
var showStrings = false;
var ilFilter = "";

for (var i = 1; i < args.Length; i++)
{
    switch (args[i])
    {
        case "--match":
            match = i + 1 < args.Length ? args[++i] : "";
            break;
        case "--members":
            showMembers = true;
            break;
        case "--strings":
            showStrings = true;
            break;
        case "--il":
            ilFilter = i + 1 < args.Length ? args[++i] : "";
            break;
        default:
            Console.Error.WriteLine($"Unknown argument: {args[i]}");
            Usage();
            return 2;
    }
}

await using var stream = File.OpenRead(assemblyPath);
using var pe = new PEReader(stream);
var reader = pe.GetMetadataReader();
var opcodes = BuildOpcodeMap();

foreach (var typeHandle in reader.TypeDefinitions)
{
    var typeDef = reader.GetTypeDefinition(typeHandle);
    var typeName = TypeFullName(reader, typeDef);
    if (!Contains(typeName, match))
    {
        continue;
    }

    Console.WriteLine(typeName);

    if (showMembers)
    {
        foreach (var fieldHandle in typeDef.GetFields())
        {
            var field = reader.GetFieldDefinition(fieldHandle);
            Console.WriteLine($"  field {reader.GetString(field.Name)}");
        }

        foreach (var methodHandle in typeDef.GetMethods())
        {
            var method = reader.GetMethodDefinition(methodHandle);
            Console.WriteLine($"  method {reader.GetString(method.Name)} rva=0x{method.RelativeVirtualAddress:X}");
        }
    }

    foreach (var methodHandle in typeDef.GetMethods())
    {
        var method = reader.GetMethodDefinition(methodHandle);
        var methodName = reader.GetString(method.Name);
        var fullMethodName = $"{typeName}.{methodName}";
        var shouldDumpIl = !string.IsNullOrEmpty(ilFilter)
            && (Contains(typeName, ilFilter) || Contains(methodName, ilFilter) || Contains(fullMethodName, ilFilter));
        var shouldDumpStrings = showStrings;

        if (!shouldDumpIl && !shouldDumpStrings)
        {
            continue;
        }

        var rva = method.RelativeVirtualAddress;
        if (rva == 0)
        {
            continue;
        }

        var body = pe.GetMethodBody(rva);
        var il = body.GetILBytes();
        if (il == null || il.Length == 0)
        {
            continue;
        }

        var decoded = DecodeIl(reader, il, opcodes).ToList();
        if (shouldDumpStrings)
        {
            foreach (var item in decoded.Where(item => item.OpName == "ldstr"))
            {
                Console.WriteLine($"  string {methodName}: {item.OperandText}");
            }
        }

        if (shouldDumpIl)
        {
            Console.WriteLine($"  il {methodName}:");
            foreach (var item in decoded)
            {
                Console.WriteLine($"    IL_{item.Offset:X4}: {item.OpName,-12} {item.OperandText}");
            }
        }
    }
}

return 0;

static bool Contains(string value, string needle)
{
    return string.IsNullOrEmpty(needle) || value.Contains(needle, StringComparison.OrdinalIgnoreCase);
}

static string TypeFullName(MetadataReader reader, TypeDefinition typeDef)
{
    var ns = reader.GetString(typeDef.Namespace);
    var name = reader.GetString(typeDef.Name);
    return string.IsNullOrEmpty(ns) ? name : $"{ns}.{name}";
}

static Dictionary<short, OpCode> BuildOpcodeMap()
{
    var map = new Dictionary<short, OpCode>();
    foreach (var field in typeof(OpCodes).GetFields(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static))
    {
        if (field.GetValue(null) is OpCode opcode)
        {
            map[opcode.Value] = opcode;
        }
    }

    return map;
}

static IEnumerable<DecodedIl> DecodeIl(MetadataReader reader, byte[] il, Dictionary<short, OpCode> opcodes)
{
    var pos = 0;
    while (pos < il.Length)
    {
        var offset = pos;
        short code = il[pos++];
        if (code == 0xFE)
        {
            code = (short)(0xFE00 | il[pos++]);
        }

        if (!opcodes.TryGetValue(code, out var opcode))
        {
            yield return new DecodedIl(offset, $"unknown_0x{code:X}", "");
            continue;
        }

        var operand = "";
        switch (opcode.OperandType)
        {
            case OperandType.InlineNone:
                break;
            case OperandType.ShortInlineI:
            case OperandType.ShortInlineVar:
                operand = il[pos].ToString();
                pos += 1;
                break;
            case OperandType.ShortInlineBrTarget:
                operand = $"IL_{pos + 1 + unchecked((sbyte)il[pos]):X4}";
                pos += 1;
                break;
            case OperandType.InlineVar:
                operand = BitConverter.ToUInt16(il, pos).ToString();
                pos += 2;
                break;
            case OperandType.InlineI:
            case OperandType.InlineBrTarget:
                var intOperand = BitConverter.ToInt32(il, pos);
                operand = opcode.OperandType == OperandType.InlineBrTarget
                    ? $"IL_{pos + 4 + intOperand:X4}"
                    : intOperand.ToString();
                pos += 4;
                break;
            case OperandType.ShortInlineR:
                operand = BitConverter.ToSingle(il, pos).ToString(System.Globalization.CultureInfo.InvariantCulture);
                pos += 4;
                break;
            case OperandType.InlineI8:
                operand = BitConverter.ToInt64(il, pos).ToString();
                pos += 8;
                break;
            case OperandType.InlineR:
                operand = BitConverter.ToDouble(il, pos).ToString(System.Globalization.CultureInfo.InvariantCulture);
                pos += 8;
                break;
            case OperandType.InlineSwitch:
                var count = BitConverter.ToInt32(il, pos);
                pos += 4 + count * 4;
                operand = $"switch({count})";
                break;
            case OperandType.InlineString:
            {
                var token = BitConverter.ToInt32(il, pos);
                pos += 4;
                operand = Quote(reader.GetUserString(MetadataTokens.UserStringHandle(token)));
                break;
            }
            case OperandType.InlineField:
            case OperandType.InlineMethod:
            case OperandType.InlineTok:
            case OperandType.InlineType:
            case OperandType.InlineSig:
            {
                var token = BitConverter.ToInt32(il, pos);
                pos += 4;
                operand = ResolveToken(reader, token);
                break;
            }
        }

        yield return new DecodedIl(offset, opcode.Name ?? $"op_{code:X}", operand);
    }
}

static string ResolveToken(MetadataReader reader, int token)
{
    var handle = MetadataTokens.EntityHandle(token);
    try
    {
        return handle.Kind switch
        {
            HandleKind.TypeDefinition => TypeFullName(reader, reader.GetTypeDefinition((TypeDefinitionHandle)handle)),
            HandleKind.TypeReference => TypeRefFullName(reader, reader.GetTypeReference((TypeReferenceHandle)handle)),
            HandleKind.MethodDefinition => MethodDefName(reader, (MethodDefinitionHandle)handle),
            HandleKind.MemberReference => MemberRefName(reader, (MemberReferenceHandle)handle),
            HandleKind.FieldDefinition => reader.GetString(reader.GetFieldDefinition((FieldDefinitionHandle)handle).Name),
            HandleKind.StandaloneSignature => $"sig 0x{token:X8}",
            _ => $"0x{token:X8}:{handle.Kind}",
        };
    }
    catch
    {
        return $"0x{token:X8}";
    }
}

static string TypeRefFullName(MetadataReader reader, TypeReference typeRef)
{
    var ns = reader.GetString(typeRef.Namespace);
    var name = reader.GetString(typeRef.Name);
    return string.IsNullOrEmpty(ns) ? name : $"{ns}.{name}";
}

static string MethodDefName(MetadataReader reader, MethodDefinitionHandle handle)
{
    var method = reader.GetMethodDefinition(handle);
    return reader.GetString(method.Name);
}

static string MemberRefName(MetadataReader reader, MemberReferenceHandle handle)
{
    var member = reader.GetMemberReference(handle);
    return reader.GetString(member.Name);
}

static string Quote(string value)
{
    return "\"" + value.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", "\\r").Replace("\n", "\\n") + "\"";
}

internal sealed record DecodedIl(int Offset, string OpName, string OperandText);
