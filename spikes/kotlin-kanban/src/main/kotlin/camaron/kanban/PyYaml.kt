package camaron.kanban

import java.time.DateTimeException
import java.time.LocalDate
import java.time.LocalDateTime
import java.util.regex.Pattern
import org.yaml.snakeyaml.DumperOptions
import org.yaml.snakeyaml.LoaderOptions
import org.yaml.snakeyaml.Yaml
import org.yaml.snakeyaml.constructor.AbstractConstruct
import org.yaml.snakeyaml.constructor.SafeConstructor
import org.yaml.snakeyaml.nodes.MappingNode
import org.yaml.snakeyaml.nodes.Node
import org.yaml.snakeyaml.nodes.NodeId
import org.yaml.snakeyaml.nodes.ScalarNode
import org.yaml.snakeyaml.nodes.Tag
import org.yaml.snakeyaml.representer.Represent
import org.yaml.snakeyaml.representer.Representer
import org.yaml.snakeyaml.resolver.Resolver

/** A YAML date, as PyYAML's `datetime.date`. */
data class PyDate(val date: LocalDate)

/** A YAML timestamp, as PyYAML's `datetime.datetime`: wall clock as written, offset kept apart. */
data class PyDateTime(val dateTime: LocalDateTime, val offsetMinutes: Int?) {
    fun isoformat(sep: Char): String {
        val d = dateTime
        val sb = StringBuilder(String.format("%04d-%02d-%02d%c%02d:%02d:%02d", d.year, d.monthValue, d.dayOfMonth, sep,
            d.hour, d.minute, d.second))
        val micro = d.nano / 1000
        if (micro != 0) sb.append(String.format(".%06d", micro))
        offsetMinutes?.let { m ->
            val sign = if (m < 0) '-' else '+'
            sb.append(String.format("%c%02d:%02d", sign, Math.abs(m) / 60, Math.abs(m) % 60))
        }
        return sb.toString()
    }
}

internal val VALUE_TAG = Tag("tag:yaml.org,2002:value")

/** PyYAML's implicit resolvers (YAML 1.1 as PyYAML reads it), matched with Python's `re.match` semantics. */
class PyResolver : Resolver() {
    override fun addImplicitResolvers() {}

    override fun resolve(kind: NodeId, value: String?, implicit: Boolean): Tag {
        if (kind == NodeId.scalar && implicit && value != null) {
            val first = if (value.isEmpty()) '\u0000' else value[0]
            for ((tag, re, firsts) in RULES) {
                if (first in firsts && re.matcher(value).lookingAt()) return tag
            }
        }
        return when (kind) {
            NodeId.scalar -> Tag.STR
            NodeId.sequence -> Tag.SEQ
            else -> Tag.MAP
        }
    }

    private companion object {
        fun py(re: String): Pattern = Pattern.compile(re, Pattern.UNIX_LINES)
        val RULES: List<Triple<Tag, Pattern, String>> = listOf(
            Triple(Tag.BOOL, py("^(?:yes|Yes|YES|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF)$"),
                "yYnNtTfFoO"),
            Triple(Tag.FLOAT, py("^(?:[-+]?(?:[0-9][0-9_]*)\\.[0-9_]*(?:[eE][-+][0-9]+)?|\\.[0-9][0-9_]*(?:[eE][-+][0-9]+)?" +
                "|[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\\.[0-9_]*|[-+]?\\.(?:inf|Inf|INF)|\\.(?:nan|NaN|NAN))$"), "-+0123456789."),
            Triple(Tag.INT, py("^(?:[-+]?0b[0-1_]+|[-+]?0[0-7_]+|[-+]?(?:0|[1-9][0-9_]*)|[-+]?0x[0-9a-fA-F_]+" +
                "|[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+)$"), "-+0123456789"),
            Triple(Tag.MERGE, py("^(?:<<)$"), "<"),
            Triple(Tag.NULL, py("^(?:~|null|Null|NULL|)$"), "~nN\u0000"),
            Triple(Tag.TIMESTAMP, py("^(?:[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]" +
                "|[0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?(?:[Tt]|[ \\t]+)[0-9][0-9]?:[0-9][0-9]:[0-9][0-9]" +
                "(?:\\.[0-9]*)?(?:[ \\t]*(?:Z|[-+][0-9][0-9]?(?::[0-9][0-9])?))?)$"), "0123456789"),
            Triple(VALUE_TAG, py("^(?:=)$"), "="),
            Triple(Tag.YAML, py("^(?:!|&|\\*)$"), "!&*"),
        )
    }
}

private val TIMESTAMP = Pattern.compile(
    "^([0-9][0-9][0-9][0-9])-([0-9][0-9]?)-([0-9][0-9]?)" +
        "(?:(?:[Tt]|[ \\t]+)([0-9][0-9]?):([0-9][0-9]):([0-9][0-9])(?:\\.([0-9]*))?" +
        "(?:[ \\t]*(Z|([-+])([0-9][0-9]?)(?::([0-9][0-9]))?))?)?$", Pattern.UNIX_LINES)

/** PyYAML's `construct_yaml_timestamp`; an impossible date is a ValueError there too, not a YAML error. */
internal fun constructTimestamp(value: String): Any {
    val m = TIMESTAMP.matcher(value)
    if (!m.lookingAt()) throw PyValueError("not a timestamp: $value")
    try {
        if (m.group(1).toInt() < 1) throw PyValueError("year 0 is out of range")
        val date = LocalDate.of(m.group(1).toInt(), m.group(2).toInt(), m.group(3).toInt())
        if (m.group(4) == null) return PyDate(date)
        val fraction = (m.group(7) ?: "").take(6).padEnd(6, '0').toInt()
        val time = LocalDateTime.of(date.year, date.monthValue, date.dayOfMonth, m.group(4).toInt(), m.group(5).toInt(),
            m.group(6).toInt(), fraction * 1000)
        val offset = when {
            m.group(9) != null -> {
                val minutes = m.group(10).toInt() * 60 + (m.group(11)?.toInt() ?: 0)
                if (minutes >= 24 * 60) throw PyValueError("offset must be a timedelta strictly between -24h and 24h")
                if (m.group(9) == "-") -minutes else minutes
            }
            m.group(8) != null -> 0
            else -> null
        }
        return PyDateTime(time, offset)
    } catch (e: DateTimeException) {
        throw PyValueError(e.message ?: "invalid date", e)
    }
}

private class PyConstructor : SafeConstructor(LoaderOptions()) {
    init {
        yamlConstructors[Tag.TIMESTAMP] = object : AbstractConstruct() {
            override fun construct(node: Node): Any = constructTimestamp((node as ScalarNode).value)
        }
    }

    // A dict keeps a repeated key where it first appeared, with the last value, and builds every value on the way.
    override fun processDuplicateKeys(node: MappingNode) {}

    override fun processDuplicateKeys(node: MappingNode, forceStringKeys: Boolean) {}

    // PyYAML's flatten_mapping reads a `=` key as text.
    override fun flattenMapping(node: MappingNode, forceStringKeys: Boolean) {
        for (tuple in node.value) if (tuple.keyNode.tag == VALUE_TAG) tuple.keyNode.tag = Tag.STR
        super.flattenMapping(node, forceStringKeys)
    }
}

private val DATEISH = pyRegex("^\\d{4}-\\d{2}-\\d{2}([ T].*)?$")

/** The representers of items.py's `_Dumper`: dates stay single-quoted text, floats as Python writes them. */
private class PyRepresenter(options: DumperOptions) : Representer(options) {
    init {
        representers[String::class.java] = Represent { data ->
            val s = data as String
            val style = if (DATEISH.matcher(s).lookingAt()) DumperOptions.ScalarStyle.SINGLE_QUOTED
            else DumperOptions.ScalarStyle.PLAIN
            representScalar(Tag.STR, s, style)
        }
        representers[java.lang.Double::class.java] = Represent { data -> representScalar(Tag.FLOAT, pyYamlFloat(data as Double)) }
        representers[PyDate::class.java] = Represent { data -> representScalar(Tag.TIMESTAMP, (data as PyDate).date.toString()) }
        representers[PyDateTime::class.java] = Represent { data ->
            representScalar(Tag.TIMESTAMP, (data as PyDateTime).isoformat(' '))
        }
    }
}

private fun pyYamlFloat(d: Double): String = when {
    d.isNaN() -> ".nan"
    d.isInfinite() -> if (d > 0) ".inf" else "-.inf"
    else -> pyFloatRepr(d).lowercase().let { if ('.' !in it && 'e' in it) it.replaceFirst("e", ".0e") else it }
}

/** `yaml.safe_load` and items.py's `yaml.dump(..., Dumper=_Dumper)` on SnakeYAML. */
object PyYaml {
    private val options = DumperOptions().apply {
        defaultFlowStyle = DumperOptions.FlowStyle.BLOCK
        indent = 2
        indicatorIndent = 2
        indentWithIndicator = true
        isAllowUnicode = true
        width = 1_000_000_000
        splitLines = false
        nonPrintableStyle = DumperOptions.NonPrintableStyle.ESCAPE
    }

    private val yaml = ThreadLocal.withInitial {
        Yaml(PyConstructor(), PyRepresenter(options), options, LoaderOptions(), PyResolver())
    }

    fun load(text: String): Any? = yaml.get().load(text)

    fun dump(data: Any?): String = yaml.get().dump(data)
}
