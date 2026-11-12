package camaron.kanban

import java.math.BigDecimal
import java.math.BigInteger
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.nio.file.Files
import java.nio.file.Path
import java.util.regex.Pattern

/** Python's ValueError: what the kit's callers catch as "bad input". */
open class PyValueError(message: String, cause: Throwable? = null) : IllegalArgumentException(message, cause)

class PyTypeError(message: String) : IllegalArgumentException(message)

private val OS = System.getProperty("os.name").lowercase()
val IS_WIN: Boolean = OS.startsWith("windows")
val IS_MAC: Boolean = OS.startsWith("mac") || OS.startsWith("darwin")

/** Python orders str by code point; String.compareTo orders UTF-16 units, which differs past U+FFFF. */
fun pyCompare(a: String, b: String): Int {
    var i = 0
    var j = 0
    while (i < a.length && j < b.length) {
        val ca = a.codePointAt(i)
        val cb = b.codePointAt(j)
        if (ca != cb) return ca.compareTo(cb)
        i += Character.charCount(ca)
        j += Character.charCount(cb)
    }
    return (i < a.length).compareTo(j < b.length)
}

val PY_ORDER: Comparator<String> = Comparator(::pyCompare)

/** Python's `re`: Unicode classes and only `\n` ends a line. Python's `\Z` must be written `\z`. */
fun pyRegex(pattern: String, flags: Int = 0): Pattern =
    Pattern.compile(pattern, Pattern.UNIX_LINES or Pattern.UNICODE_CHARACTER_CLASS or flags)

fun pyIsSpace(cp: Int): Boolean = Character.isWhitespace(cp) || Character.isSpaceChar(cp) || cp == 0x85

private fun stripSet(chars: String?): (Int) -> Boolean =
    if (chars == null) ::pyIsSpace else { cp -> chars.codePoints().anyMatch { it == cp } }

fun pyLStrip(s: String, chars: String? = null): String {
    val drop = stripSet(chars)
    var i = 0
    while (i < s.length) {
        val cp = s.codePointAt(i)
        if (!drop(cp)) break
        i += Character.charCount(cp)
    }
    return s.substring(i)
}

fun pyRStrip(s: String, chars: String? = null): String {
    val drop = stripSet(chars)
    var end = s.length
    while (end > 0) {
        val cp = s.codePointBefore(end)
        if (!drop(cp)) break
        end -= Character.charCount(cp)
    }
    return s.substring(0, end)
}

fun pyStrip(s: String, chars: String? = null): String = pyRStrip(pyLStrip(s, chars), chars)

/** `str.split()` with no separator: runs of whitespace, no empty parts. */
fun pySplitWs(s: String): List<String> {
    val parts = mutableListOf<String>()
    val cur = StringBuilder()
    s.codePoints().forEach { cp ->
        if (pyIsSpace(cp)) {
            if (cur.isNotEmpty()) parts += cur.toString().also { cur.setLength(0) }
        } else cur.appendCodePoint(cp)
    }
    if (cur.isNotEmpty()) parts += cur.toString()
    return parts
}

fun String.cpLen(): Int = codePointCount(0, length)
fun String.cpTake(n: Int): String = if (n >= cpLen()) this else substring(0, offsetByCodePoints(0, n))
fun String.cpAt(n: Int): String {
    val start = offsetByCodePoints(0, n)
    return substring(start, start + Character.charCount(codePointAt(start)))
}

fun pyTruthy(v: Any?): Boolean = when (v) {
    null -> false
    is Boolean -> v
    is BigInteger -> v.signum() != 0
    is BigDecimal -> v.signum() != 0
    is Number -> v.toDouble() != 0.0
    is String -> v.isNotEmpty()
    is Collection<*> -> v.isNotEmpty()
    is Map<*, *> -> v.isNotEmpty()
    is ByteArray -> v.isNotEmpty()
    else -> true
}

fun pyStr(v: Any?): String = when (v) {
    null -> "None"
    is Boolean -> if (v) "True" else "False"
    is String -> v
    is Double -> pyFloatRepr(v)
    is Float -> pyFloatRepr(v.toDouble())
    is PyDate -> v.date.toString()
    is PyDateTime -> v.isoformat(' ')
    is List<*> -> v.joinToString(", ", "[", "]") { pyRepr(it) }
    is Map<*, *> -> v.entries.joinToString(", ", "{", "}") { "${pyRepr(it.key)}: ${pyRepr(it.value)}" }
    else -> v.toString()
}

private val NON_PRINTABLE = setOf(Character.CONTROL, Character.FORMAT, Character.SURROGATE, Character.PRIVATE_USE,
    Character.UNASSIGNED, Character.LINE_SEPARATOR, Character.PARAGRAPH_SEPARATOR, Character.SPACE_SEPARATOR).map { it.toInt() }

/** `str.isprintable()` for one code point (the JDK's Unicode tables, which may lag Python's). */
fun pyIsPrintable(cp: Int): Boolean = cp == ' '.code || Character.getType(cp) !in NON_PRINTABLE

fun pyRepr(v: Any?): String {
    if (v !is String) return pyStr(v)
    val q = if ('\'' in v && '"' !in v) '"' else '\''
    val sb = StringBuilder().append(q)
    v.codePoints().forEach { cp ->
        when {
            cp == q.code || cp == '\\'.code -> sb.append('\\').appendCodePoint(cp)
            cp == '\n'.code -> sb.append("\\n")
            cp == '\r'.code -> sb.append("\\r")
            cp == '\t'.code -> sb.append("\\t")
            pyIsPrintable(cp) -> sb.appendCodePoint(cp)
            cp < 0x100 -> sb.append(String.format("\\x%02x", cp))
            cp < 0x10000 -> sb.append(String.format("\\u%04x", cp))
            else -> sb.append(String.format("\\U%08x", cp))
        }
    }
    return sb.append(q).toString()
}

/** `repr(float)`: shortest round-trip digits, exponent form outside 1e-4..1e16. */
fun pyFloatRepr(d: Double): String {
    if (d.isNaN()) return "nan"
    if (d.isInfinite()) return if (d > 0) "inf" else "-inf"
    if (d == 0.0) return if (1.0 / d < 0) "-0.0" else "0.0"
    val bd = BigDecimal(d.toString()).stripTrailingZeros()
    val digits = bd.unscaledValue().abs().toString()
    val exp10 = digits.length - 1 - bd.scale()
    val sign = if (d < 0) "-" else ""
    if (exp10 < -4 || exp10 >= 16) {
        val mantissa = if (digits.length > 1) digits[0] + "." + digits.substring(1) else digits
        val e = if (exp10 < 0) "-" + String.format("%02d", -exp10) else "+" + String.format("%02d", exp10)
        return "${sign}${mantissa}e$e"
    }
    val plain = bd.abs().toPlainString()
    return sign + if ('.' in plain) plain else "$plain.0"
}

/** `json.dumps(s, ensure_ascii=...)` for a str. */
fun pyJsonString(s: String, ensureAscii: Boolean): String {
    val sb = StringBuilder("\"")
    for (ch in s) {
        when {
            ch == '"' -> sb.append("\\\"")
            ch == '\\' -> sb.append("\\\\")
            ch == '\n' -> sb.append("\\n")
            ch == '\r' -> sb.append("\\r")
            ch == '\t' -> sb.append("\\t")
            ch == '\b' -> sb.append("\\b")
            ch == '\u000c' -> sb.append("\\f")
            ch < ' ' -> sb.append(String.format("\\u%04x", ch.code))
            ensureAscii && ch > '~' -> sb.append(String.format("\\u%04x", ch.code))
            else -> sb.append(ch)
        }
    }
    return sb.append('"').toString()
}

/** `json.dumps(value)` with Python's default separators. */
fun pyJson(v: Any?, ensureAscii: Boolean = true): String = when (v) {
    null -> "null"
    is Boolean -> v.toString()
    is String -> pyJsonString(v, ensureAscii)
    is Int, is Long, is Short, is Byte, is BigInteger -> v.toString()
    is Double -> when {
        v.isNaN() -> "NaN"
        v.isInfinite() -> if (v > 0) "Infinity" else "-Infinity"
        else -> pyFloatRepr(v)
    }
    is List<*> -> v.joinToString(", ", "[", "]") { pyJson(it, ensureAscii) }
    is Map<*, *> -> v.entries.joinToString(", ", "{", "}") {
        pyJsonString(pyJsonKey(it.key), ensureAscii) + ": " + pyJson(it.value, ensureAscii)
    }
    else -> throw PyTypeError("Object of type ${v.javaClass.simpleName} is not JSON serializable")
}

/** How `json.dumps` turns a dict key into a string: `True` is "true", `None` is "null". */
private fun pyJsonKey(k: Any?): String = when (k) {
    null -> "null"
    is Boolean -> k.toString()
    is Double -> pyJson(k)
    else -> pyStr(k)
}

private val INT_LITERAL = pyRegex("[+-]?\\d+(?:_\\d+)*")

/** `int(v)` for the values a YAML reader hands back. */
fun pyInt(v: Any?): Long = when (v) {
    is Boolean -> if (v) 1L else 0L
    is Int -> v.toLong()
    is Long -> v
    is BigInteger -> try { v.longValueExact() } catch (e: ArithmeticException) { throw PyValueError("int too large") }
    is Double -> if (v.isNaN() || v.isInfinite()) throw PyValueError("cannot convert float $v to integer") else v.toLong()
    is String -> {
        val s = pyStrip(v)
        if (!INT_LITERAL.matcher(s).matches()) throw PyValueError("invalid literal for int() with base 10: ${pyRepr(v)}")
        try { BigInteger(s.replace("_", "")).longValueExact() } catch (e: ArithmeticException) { throw PyValueError("int too large") }
    }
    null -> throw PyTypeError("int() argument must be a string or a number, not 'NoneType'")
    else -> throw PyTypeError("int() argument must be a string or a number")
}

/** Iterating a value the way a Python `for` does: a str yields characters, a dict its keys. */
fun pyIter(v: Any?): List<Any?> = when (v) {
    is List<*> -> v
    is Set<*> -> v.toList()
    is Map<*, *> -> v.keys.toList()
    is String -> v.codePoints().toArray().map { String(Character.toChars(it)) }
    else -> throw PyTypeError("object is not iterable")
}

/** `Path.read_text(encoding="utf-8")`: strict decoding and universal newlines. */
fun readTextPy(path: Path): String {
    val decoder = Charsets.UTF_8.newDecoder()
        .onMalformedInput(CodingErrorAction.REPORT)
        .onUnmappableCharacter(CodingErrorAction.REPORT)
    val text = decoder.decode(ByteBuffer.wrap(Files.readAllBytes(path))).toString()
    return text.replace("\r\n", "\n").replace('\r', '\n')
}

fun writeTextLf(path: Path, text: String) {
    Files.write(path, text.toByteArray(Charsets.UTF_8))
}
