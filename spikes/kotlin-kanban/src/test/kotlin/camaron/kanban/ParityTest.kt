package camaron.kanban

import com.fasterxml.jackson.core.json.JsonReadFeature
import com.fasterxml.jackson.databind.json.JsonMapper
import java.nio.file.Files
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.Test

/** Checks the port against the Python kit's outputs on the same seeded inputs (parity/gen_golden.py writes them). */
class ParityTest {
    private val goldenFile = KIT_ROOT.resolve("spikes/kotlin-kanban/parity/golden.json")

    /** Divergences understood and left open (see docs/research/kotlin-migration-spike.md): a ratchet, never a free pass.
     * `load`: SnakeYAML's scanner takes a tab inside a plain scalar, PyYAML's refuses the file.
     * `item_dump`: SnakeYAML's Emitter (a final class) escapes BOM, DEL, NBSP and folds multi-line scalars its own way. */
    private val known = mapOf("load" to 2, "item_dump" to 80)
    private val iso = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss").withZone(ZoneOffset.UTC)

    private class Tally(val name: String) {
        var total = 0
        var mismatches = 0
        val examples = mutableListOf<String>()
        val all = mutableListOf<String>()
        val raisePairs = sortedMapOf<String, Int>()
    }

    private fun outcome(fn: () -> Any?): Map<String, Any?> = try {
        mapOf("ok" to fn())
    } catch (e: Exception) {
        mapOf("raises" to e.javaClass.simpleName, "message" to e.message)
    }

    private fun check(t: Tally, input: Any?, expected: Map<*, *>, fn: () -> Any?) {
        t.total++
        val actual = outcome(fn)
        val same = when {
            "raises" in expected && "raises" in actual -> {
                val pair = "${expected["raises"]} -> ${actual["raises"]}"
                t.raisePairs[pair] = (t.raisePairs[pair] ?: 0) + 1
                true
            }
            "ok" in expected && "ok" in actual -> pyJson(expected["ok"]) == pyJson(actual["ok"])
            else -> false
        }
        if (!same) {
            t.mismatches++
            t.all += pyJson(linkedMapOf("kind" to t.name, "in" to input, "python" to expected, "kotlin" to actual))
            if (t.examples.size < 6) {
                t.examples += "  in:       ${pyJson(input)}\n  python:   ${pyJson(expected)}\n  kotlin:   ${pyJson(actual)}"
            }
        }
    }

    @Suppress("UNCHECKED_CAST")
    private fun node(m: Map<*, *>) = Node(
        id = m["id"] as String, status = m["status"] as String, priority = m["priority"] as String?,
        touches = m["touches"] as List<String>, repos = m["repos"] as List<String>, deps = m["deps"] as List<String>,
        archived = m["archived"] as Boolean, parent = m["parent"] as String?,
    )

    @Suppress("UNCHECKED_CAST")
    private fun cardOf(m: Map<*, *>) = Card(m["uid"] as String, m["status"] as String, (m["ordinal"] as Number).toLong(),
        m["assignee"] as List<String>, LinkedHashMap(m["t"] as Map<String, String>))

    private fun cardsToPy(cards: Map<String, Card>) = cards.mapValuesTo(LinkedHashMap()) { (_, c) ->
        linkedMapOf("uid" to c.uid, "status" to c.status, "ordinal" to c.ordinal, "assignee" to c.assignee, "t" to c.t)
    }

    private fun reasonToPy(r: Reason): Map<String, Any?> =
        if (r.kind == "wave") linkedMapOf("kind" to "wave", "wave" to r.wave)
        else linkedMapOf<String, Any?>("id" to r.id, "kind" to r.kind).apply { r.files?.let { put("files", it) } }

    private fun waitingToPy(w: Waiting) = linkedMapOf("id" to w.id, "blocked_by" to w.blockedBy.map(::reasonToPy))

    @Test
    @Suppress("UNCHECKED_CAST")
    fun `matches the python kit on the golden corpus`() {
        assumeTrue(Files.exists(goldenFile), "run parity/gen_golden.py first")
        val mapper = JsonMapper.builder().enable(JsonReadFeature.ALLOW_NON_NUMERIC_NUMBERS).build()
        val golden = mapper.readValue(goldenFile.toFile(), Map::class.java) as Map<String, List<Map<String, Any?>>>
        val tallies = linkedMapOf<String, Tally>()
        fun each(name: String, body: (Tally, Map<String, Any?>) -> Unit) {
            val t = tallies.getOrPut(name) { Tally(name) }
            golden.getValue(name).forEach { body(t, it) }
        }
        fun out(c: Map<String, Any?>, key: String = "out") = c[key] as Map<*, *>

        each("scalar") { t, c -> check(t, c["in"], out(c)) { scalar(c["in"] as String) } }
        each("dump") { t, c ->
            val cards = (c["cards"] as Map<String, Map<*, *>>).mapValuesTo(LinkedHashMap()) { cardOf(it.value) }
            check(t, c["cards"], out(c)) { dumpBoard(cards) }
        }
        each("load") { t, c -> check(t, c["in"], out(c)) { pyJson(cardsToPy(loadBoard(c["in"] as String))) } }
        each("item_dump") { t, c ->
            check(t, c["fm"], out(c)) { serializeItem(Item(c["fm"] as Map<Any?, Any?>, c["body"] as String)) }
        }
        each("item_parse") { t, c ->
            check(t, c["in"], out(c)) { parseItem(c["in"] as String).let { pyJson(linkedMapOf("fm" to it.fm, "body" to it.body)) } }
        }
        each("title") { t, c -> check(t, c["in"], out(c)) { fileName("WI-7", c["in"] as String) } }
        each("merge") { t, c ->
            val (b, o, th) = c["in"] as List<String>
            check(t, c["in"], out(c)) { mergeBoards(b, o, th).let { listOf(it.first, it.second) } }
        }
        each("graph") { t, c ->
            val nodes = (c["nodes"] as List<Map<*, *>>).map(::node)
            val groups = c["groups"] as Map<String, String>?
            for (agent in listOf(true, false)) {
                check(t, c["nodes"], out(c, "waves_${if (agent) "True" else "False"}")) { waves(nodes, agent) }
                check(t, c["nodes"], out(c, "ready_${if (agent) "True" else "False"}")) {
                    val waiting = mutableListOf<Waiting>()
                    listOf(ready(nodes, agent, waiting = waiting), waiting.map(::waitingToPy))
                }
            }
            check(t, c["nodes"], out(c, "blocked")) { nodes.map { n -> blockedBy(n, nodes, agent = true).map(::reasonToPy) } }
            check(t, c["nodes"], out(c, "conflicts")) { nodes.map { n -> conflicts(n, nodes, groups).map(::reasonToPy) } }
            check(t, c["nodes"], mapOf("ok" to c["containers"])) { containers(nodes).sortedWith(PY_ORDER) }
            check(t, c["nodes"], mapOf("ok" to c["sccs"])) { sccs(nodes.associate { it.id to it.deps }) }
        }
        each("touch") { t, c -> check(t, c["in"], out(c)) { normTouch(c["in"] as String, c["fold"] as Boolean) } }
        each("overlap") { t, c ->
            check(t, listOf(c["a"], c["b"], c["fold"]), mapOf("ok" to c["out"])) {
                overlap((c["a"] as List<String>).toSet(), (c["b"] as List<String>).toSet(), c["fold"] as Boolean).sortedWith(PY_ORDER)
            }
        }
        each("stamp") { t, c -> check(t, c["in"], out(c)) { iso.format(stampTime(c["in"] as String)) + "+00:00" } }
        each("order") { t, c -> check(t, c["in"], mapOf("ok" to c["out"])) { (c["in"] as List<String>).sortedWith(ID_ORDER) } }
        each("place") { t, c ->
            val col = (c["col"] as List<List<Any>>).map { it[0] as String to (it[1] as Number).toLong() }
            val kw = c["kw"] as Map<String, String>
            check(t, c["col"], out(c)) { place(col, before = kw["before"], after = kw["after"]) }
        }

        val report = StringBuilder()
        for (t in tallies.values) {
            report.append(String.format("%-11s %6d cases  %4d mismatches", t.name, t.total, t.mismatches))
            if (t.raisePairs.isNotEmpty()) report.append("   raises: ").append(t.raisePairs)
            report.append('\n')
            t.examples.forEach { report.append(it).append('\n') }
        }
        val total = tallies.values.sumOf { it.total }
        val bad = tallies.values.sumOf { it.mismatches }
        report.append("TOTAL $total cases, $bad mismatches\n")
        val target = KIT_ROOT.resolve("spikes/kotlin-kanban/target/parity-report.txt")
        Files.createDirectories(target.parent)
        Files.write(target, report.toString().toByteArray(Charsets.UTF_8))
        Files.write(target.resolveSibling("parity-mismatches.jsonl"),
            tallies.values.flatMap { it.all }.joinToString("\n").toByteArray(Charsets.UTF_8))
        System.err.println(report)
        val unexpected = tallies.values.filter { it.mismatches > (known[it.name] ?: 0) }.map { "${it.name}=${it.mismatches}" }
        assertTrue(unexpected.isEmpty(), "new parity mismatches: $unexpected (see target/parity-report.txt)")
    }
}
