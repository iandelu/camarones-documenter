package camaron.kanban

import java.time.Instant
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

fun card(uid: String = "01jb7p0a", status: String = "Ready", ordinal: Long = 1000, assignee: List<String> = emptyList(),
         t: Map<String, String> = emptyMap()) = Card(uid, status, ordinal, assignee, LinkedHashMap(t))

class StateTest {
    @Test
    fun `dump is one line per card sorted`() {
        val cards = linkedMapOf(
            "WI-10" to card("aaaaaaaa", ordinal = 3000),
            "WI-2" to card("bbbbbbbb", "In Progress", 1000, listOf("ana"), mapOf("status" to "2026-10-20T09:00:00Z luis@x")),
            "WI-3" to card("12345678", ordinal = 2000),
        )
        val text = dumpBoard(cards)
        val lines = text.lines().dropLast(1)
        assertEquals(listOf("version: 1", "cards:"), lines.take(2))
        assertEquals(listOf("WI-2", "WI-3", "WI-10"), lines.drop(2).map { it.substringBefore(':').trim() })
        assertTrue(text.endsWith("\n") && lines.size == 5)
        assertTrue(lines[2].startsWith("  WI-2: {uid: bbbbbbbb, status: In Progress, ordinal: 1000, assignee: [ana], t: {"))
        assertEquals(cards, loadBoard(text))
    }

    @Test
    fun `load rejects garbage`() {
        assertThrows<IllegalArgumentException> { loadBoard("cards: [1") }
        assertThrows<IllegalArgumentException> { loadBoard("version: 2\ncards: {}\n") }
    }

    @Test
    fun `next id`() {
        assertEquals("WI-10", nextId(listOf("WI-1", "WI-9", "WI-3~ab")))
        assertEquals("WI-1", nextId(emptyList()))
    }

    @Test
    fun `id key is natural and temp keys follow`() {
        assertEquals(listOf("WI-2", "WI-10", "WI-42", "WI-42~zz"), listOf("WI-10", "WI-42~zz", "WI-2", "WI-42").sortedWith(ID_ORDER))
    }

    @Test
    fun `place at end and start`() {
        val col = listOf("a" to 1000L, "b" to 2000L)
        assertEquals(mapOf("*" to 3000L), place(col))
        assertEquals(mapOf("*" to 500L), place(col, before = "a"))
        assertEquals(mapOf("*" to 1500L), place(col, after = "a"))
        assertEquals(mapOf("*" to 1000L), place(emptyList()))
    }

    @Test
    fun `place rebalances when no room`() {
        assertEquals(mapOf("*" to 2000L, "b" to 3000L), place(listOf("a" to 1000L, "b" to 1001L), after = "a"))
        assertEquals(mapOf("*" to 1000L, "a" to 2000L, "b" to 3000L), place(listOf("a" to 1L, "b" to 5L), before = "a"))
    }

    @Test
    fun `stamp format`() {
        val now = Instant.parse("2026-10-24T10:12:00Z")
        val c = card().stamped("status", "ana@x", now)
        assertEquals("2026-10-24T10:12:00Z ana@x", c.t["status"])
        assertEquals(now, stampTime(c.t.getValue("status")))
    }

    @Test
    fun `uid shape`() {
        assertTrue(Regex("[0-9a-hjkmnp-tv-z]{8}").matches(newUid()))
    }

    @Test
    fun `values that yaml would misread survive`() {
        val cards = mapOf("WI-1" to card("12345678", assignee = listOf("a b", "x:y", "null"),
            t = mapOf("status" to "2026-10-24T10:12:00Z a@x")))
        assertEquals(cards, loadBoard(dumpBoard(cards)))
    }
}
