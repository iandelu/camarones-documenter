package camaron.kanban

import java.math.BigInteger
import java.security.SecureRandom
import java.time.DateTimeException
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.regex.Pattern
import org.yaml.snakeyaml.error.YAMLException

val STATUSES = listOf("Backlog", "Ready", "In Progress", "In Review", "Done", "Blocked")
val TYPES = listOf("epic", "story", "bug", "spike", "task")
val PRIORITIES = listOf("P0", "P1", "P2", "P3")
const val PREFIX = "WI"

const val ORDINAL_STEP = 1000L
private const val CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"
private val ID = pyRegex("^(.*?)-(\\d+)(~.*)?$")
private val SPECIAL = ":,{}[]#\"'&*!|>%@`".toSet()
private val RANDOM = SecureRandom()
private val STAMP_OUT = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'").withZone(ZoneOffset.UTC)
private val STAMP_IN = pyRegex("(\\d\\d\\d\\d)-(1[0-2]|0[1-9]|[1-9])-(3[01]|[12]\\d|0[1-9]|[1-9]| [1-9])" +
    "T(2[0-3]|[0-1]\\d|\\d):([0-5]\\d|\\d):(6[0-1]|[0-5]\\d|\\d)Z", Pattern.CASE_INSENSITIVE)

class BoardError(message: String, cause: Throwable? = null) : PyValueError(message, cause)

/** One line of board.yaml: the kit's state for a card. */
data class Card(
    val uid: String,
    val status: String,
    val ordinal: Long,
    val assignee: List<String> = emptyList(),
    val t: Map<String, String> = emptyMap(),
)

/** Natural order of item ids: WI-2 < WI-10; a temporary key WI-42~uid sorts right after WI-42. */
data class IdKey(val prefix: String, val number: BigInteger, val suffix: String) : Comparable<IdKey> {
    override fun compareTo(other: IdKey): Int {
        pyCompare(prefix, other.prefix).let { if (it != 0) return it }
        number.compareTo(other.number).let { if (it != 0) return it }
        return pyCompare(suffix, other.suffix)
    }
}

fun idKey(itemId: String): IdKey {
    val m = ID.matcher(itemId)
    return if (m.lookingAt()) IdKey(m.group(1), BigInteger(m.group(2)), m.group(3) ?: "")
    else IdKey(itemId, BigInteger.ZERO, "")
}

val ID_ORDER: Comparator<String> = compareBy(::idKey)

fun newUid(): String = String(CharArray(8) { CROCKFORD[RANDOM.nextInt(CROCKFORD.length)] })

fun nextId(existing: Iterable<String>, prefix: String = PREFIX): String {
    var top = BigInteger.ZERO
    for (i in existing) {
        val m = ID.matcher(i)
        if (m.lookingAt() && m.group(1) == prefix) top = top.max(BigInteger(m.group(2)))
    }
    return "$prefix-${top + BigInteger.ONE}"
}

fun Card.stamped(field: String, who: String, now: Instant): Card =
    copy(t = LinkedHashMap(t).apply { put(field, "${STAMP_OUT.format(now)} $who") })

fun stampTime(value: String): Instant {
    val m = STAMP_IN.matcher(value.substringBefore(' '))
    if (!m.matches()) throw PyValueError("time data ${pyRepr(value)} does not match format '%Y-%m-%dT%H:%M:%SZ'")
    val f = (1..6).map { Integer.parseInt(m.group(it).trim()) }
    if (f[0] < 1) throw PyValueError("year ${f[0]} is out of range")
    try {
        return LocalDateTime.of(f[0], f[1], f[2], f[3], f[4], f[5]).toInstant(ZoneOffset.UTC)
    } catch (e: DateTimeException) {
        throw PyValueError(e.message ?: "invalid stamp", e)
    }
}

// --- reader / writer ---

private fun isOne(v: Any?): Boolean = v == true || (v is Number && v !is Double && v.toLong() == 1L) || v == 1.0

fun loadBoard(text: String): LinkedHashMap<String, Card> {
    val data = try {
        PyYaml.load(text)
    } catch (e: YAMLException) {
        throw BoardError("board.yaml is not valid YAML: ${e.message}", e)
    }
    if (data !is Map<*, *> || !isOne(data["version"])) throw BoardError("board.yaml: expected a mapping with version: 1")
    val raw = data["cards"].takeIf(::pyTruthy) ?: emptyMap<Any?, Any?>()
    if (raw !is Map<*, *>) throw BoardError("board.yaml: cards must be a mapping")
    val cards = LinkedHashMap<String, Card>()
    for ((key, c) in raw) {
        if (c !is Map<*, *>) throw BoardError("board.yaml: card ${pyStr(key)} is not a mapping")
        try {
            if ("uid" !in c || "status" !in c || "ordinal" !in c) throw PyValueError("missing field")
            val t = c["t"].takeIf(::pyTruthy) ?: emptyMap<Any?, Any?>()
            if (t !is Map<*, *>) throw PyTypeError("t is not a mapping")
            cards[pyStr(key)] = Card(
                uid = pyStr(c["uid"]),
                status = pyStr(c["status"]),
                ordinal = pyInt(c["ordinal"]),
                assignee = pyIter(c["assignee"].takeIf(::pyTruthy) ?: emptyList<Any?>()).map(::pyStr),
                t = t.entries.associateTo(LinkedHashMap()) { pyStr(it.key) to pyStr(it.value) },
            )
        } catch (e: IllegalArgumentException) {
            throw BoardError("board.yaml: card ${pyStr(key)} is malformed (${e.message})", e)
        }
    }
    return cards
}

internal fun scalar(s: String): String {
    // PyYAML's scanner refuses a tab inside a plain scalar; SnakeYAML's takes it.
    var plain = s == pyStrip(s) && s.isNotEmpty() && s[0] !in SPECIAL && s.none { it in ":,{}[]#\n\t" }
    if (plain) {
        plain = try {
            PyYaml.load(s) == s
        } catch (e: YAMLException) {
            false
        }
    }
    return if (plain) s else pyJsonString(s, ensureAscii = false)
}

fun dumpBoard(cards: Map<String, Card>): String {
    val lines = mutableListOf("version: 1", "cards:")
    for (key in cards.keys.sortedWith(ID_ORDER)) {
        val c = cards.getValue(key)
        val assignee = c.assignee.joinToString(", ") { scalar(it) }
        val t = c.t.entries.joinToString(", ") { "${scalar(it.key)}: ${scalar(it.value)}" }
        lines += "  ${scalar(key)}: {uid: ${scalar(c.uid)}, status: ${scalar(c.status)}, " +
            "ordinal: ${c.ordinal}, assignee: [$assignee], t: {$t}}"
    }
    return lines.joinToString("\n") + "\n"
}

// --- ordinals ---

/** Ordinal for a card dropped in `column`: at the end, or before/after an anchor. `"*"` is the new card; when there is
 * no room between neighbours the column is rebalanced and every card whose ordinal changes is included too. */
fun place(column: List<Pair<String, Long>>, before: String? = null, after: String? = null): Map<String, Long> {
    val col = column.sortedBy { it.second }
    val ids = col.map { it.first }
    val anchor = before ?: after
    val pos = when {
        anchor == null -> col.size
        anchor !in ids -> throw PyValueError("$anchor is not in the column")
        else -> ids.indexOf(anchor) + if (before != null) 0 else 1
    }
    val lo = if (pos > 0) col[pos - 1].second else 0L
    if (pos >= col.size) return mapOf("*" to lo + ORDINAL_STEP)
    val hi = col[pos].second
    val mid = Math.floorDiv(lo + hi, 2L)
    if (lo < mid && mid < hi) return mapOf("*" to mid)
    val out = LinkedHashMap<String, Long>()
    val order = ids.subList(0, pos) + "*" + ids.subList(pos, ids.size)
    val old = col.toMap()
    order.forEachIndexed { n, i ->
        val target = (n + 1) * ORDINAL_STEP
        if (i == "*" || old[i] != target) out[i] = target
    }
    return out
}
