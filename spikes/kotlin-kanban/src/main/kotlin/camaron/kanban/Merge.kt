package camaron.kanban

import java.io.IOException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.time.Instant
import kotlin.system.exitProcess

private val FIELDS = listOf("status", "ordinal", "assignee")

private fun Card.field(f: String): Any = when (f) {
    "status" -> status
    "ordinal" -> ordinal
    else -> assignee
}

private fun parse(text: String): Map<String, Card> {
    if (pyStrip(text).isEmpty()) return emptyMap()
    try {
        return loadBoard(text)
    } catch (e: IllegalArgumentException) {
        throw e
    } catch (e: RuntimeException) {
        throw BoardError("board.yaml is malformed (${e.message})", e)
    }
}

private data class Rank(val time: Instant, val author: String, val value: String) : Comparable<Rank> {
    override fun compareTo(other: Rank): Int {
        time.compareTo(other.time).let { if (it != 0) return it }
        pyCompare(author, other.author).let { if (it != 0) return it }
        return pyCompare(value, other.value)
    }
}

/** Who wins a field changed on both sides: latest stamp, then author, then value (same pick on every machine). */
private fun rank(card: Card, field: String): Rank {
    val raw = card.t[field] ?: return Rank(Instant.MIN, "", pyJson(card.field(field)))
    return Rank(stampTime(raw), if (' ' in raw) raw.substringAfter(' ') else "", pyJson(card.field(field)))
}

/** Older card first (earliest stamp it carries), uid as the last word. */
private val BIRTH: Comparator<Card> = compareBy<Card> { c -> c.t.values.map(::stampTime).minOrNull() ?: Instant.MAX }
    .thenBy(PY_ORDER) { it.uid }

private val STAMP_ORDER: Comparator<String> = compareBy<String> { stampTime(it) }.thenBy(PY_ORDER) { it }

private fun mergeCard(base: Card?, ours: Card, theirs: Card): Card {
    val t = LinkedHashMap<String, String>()
    val picked = HashMap<String, Card>()
    for (f in FIELDS) {
        val oCh = base == null || ours.field(f) != base.field(f)
        val tCh = base == null || theirs.field(f) != base.field(f)
        val src = if (oCh && tCh) (if (rank(ours, f) >= rank(theirs, f)) ours else theirs) else if (tCh) theirs else ours
        picked[f] = src
        src.t[f]?.let { t[f] = it }
    }
    for (k in (ours.t.keys + theirs.t.keys).sortedWith(PY_ORDER)) {
        if (k in FIELDS) continue
        t[k] = listOfNotNull(ours.t[k], theirs.t[k]).maxWith(STAMP_ORDER)
    }
    return Card(
        uid = ours.uid,
        status = picked.getValue("status").status,
        ordinal = picked.getValue("ordinal").ordinal,
        assignee = picked.getValue("assignee").assignee.toList(),
        t = t.entries.sortedWith(compareBy(PY_ORDER) { it.key }).associateTo(LinkedHashMap()) { it.key to it.value },
    )
}

/** Merges per card and per field so two people's moves never conflict. Returns the board text and a log. */
fun mergeBoards(base: String, ours: String, theirs: String): Pair<String, List<String>> {
    val b = parse(base)
    val o = parse(ours)
    val t = parse(theirs)
    val log = mutableListOf<String>()
    val cards = try {
        mergeAll(b, o, t, log)
    } catch (e: IllegalArgumentException) {
        throw e
    } catch (e: RuntimeException) {
        throw BoardError("board.yaml: cannot merge (${e.message})", e)
    }
    return dumpBoard(cards) to log
}

private fun mergeAll(b: Map<String, Card>, o: Map<String, Card>, t: Map<String, Card>, log: MutableList<String>): Map<String, Card> {
    val cards = LinkedHashMap<String, Card>()
    val keys = (b.keys + o.keys + t.keys).sortedWith(compareBy<String> { idKey(it) }.thenBy(PY_ORDER) { it })
    for (key in keys) {
        val base = b[key]
        val a = o[key]
        val c = t[key]
        when {
            a == null && c == null -> continue
            a == null || c == null -> {
                val side = a ?: c!!
                if (base != null && side == base) continue
                if (base != null) log += "$key: removed on one side but changed on the other; kept"
                cards[key] = side
            }
            a.uid != c.uid -> {
                val (first, second) = listOf(a, c).sortedWith(BIRTH)
                cards[key] = first
                cards["$key~${second.uid}"] = second
                log += "$key: created on both sides; the newer one is kept as $key~${second.uid}"
            }
            else -> cards[key] = mergeCard(base, a, c)
        }
    }
    return cards
}

// --- what git runs ---

/** `board merge-driver %O %A %B`: result into `ours`, log to stderr; 1 leaves `ours` untouched (git conflicts). */
fun driver(base: Path, ours: Path, theirs: Path): Int {
    val result = try {
        val texts = listOf(base, ours, theirs).map { if (Files.exists(it)) readTextPy(it) else "" }
        mergeBoards(texts[0], texts[1], texts[2])
    } catch (e: IllegalArgumentException) {
        System.err.println("board merge: ${e.message}")
        return 1
    } catch (e: IOException) {
        System.err.println("board merge: $e")
        return 1
    }
    writeTextLf(ours, result.first)
    for (line in result.second) System.err.println("board merge: $line")
    return 0
}

/** The `merge.camaron-board.driver` value: git runs it through `sh` on every OS, so POSIX paths in double quotes. */
fun driverCommand(launcher: List<String>): String {
    fun q(part: String): String {
        var p = part.replace('\\', '/')
        for (ch in listOf("\"", "$", "`")) p = p.replace(ch, "\\" + ch)
        return "\"$p\""
    }
    return (launcher.map(::q) + "board merge-driver %O %A %B").joinToString(" ")
}

object MergeDriverMain {
    @JvmStatic
    fun main(args: Array<String>) {
        val (b, o, t) = args.takeLast(3).map { Paths.get(it) }
        exitProcess(driver(b, o, t))
    }
}
