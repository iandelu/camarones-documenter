package camaron.kanban

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.io.TempDir

val KIT_ROOT: Path = Paths.get(System.getProperty("kit.root", "../.."))
private val FIX = KIT_ROOT.resolve("tests/fixtures/backlogmd")

private fun wi42(): String = String(Files.readAllBytes(FIX.resolve("wi-42 - Idempotent PaymentRequested handling.md")), Charsets.UTF_8)

class ItemsTest {
    @Test
    fun `round trip keeps backlogmd bytes`() {
        val text = wi42()
        assertEquals(text, serializeItem(parseItem(text)))
    }

    @Test
    fun `field order then unknown then x fields`() {
        val out = serializeItem(Item(linkedMapOf("x-uid" to "u", "title" to "T", "id" to "WI-1", "zzz" to 1, "status" to "Ready"), "b\n"))
        val keys = out.split("---\n")[1].lines().filter { it.isNotEmpty() }.map { it.substringBefore(':') }
        assertEquals(listOf("id", "title", "status", "zzz", "x-uid"), keys)
    }

    @Test
    fun `empty lists and none`() {
        val out = serializeItem(Item(linkedMapOf("id" to "WI-1", "title" to "T", "labels" to emptyList<String>(), "assignee" to null,
            "created_date" to "2026-10-24 10:12", "documentation" to listOf("a", "b")), ""))
        assertTrue("labels: []\n" in out && "assignee" !in out)
        assertTrue("documentation:\n  - a\n  - b\n" in out, out)
        assertTrue("created_date: '2026-10-24 10:12'\n" in out)
        assertTrue(out.startsWith("---\n") && out.endsWith("---\n\n"))
    }

    @Test
    fun `unquoted dates stay text`() {
        assertEquals("2026-10-24", parseItem("---\nid: WI-1\ncreated_date: 2026-10-24\n---\n").fm["created_date"])
    }

    @Test
    fun `crlf parses like lf`() {
        val raw = String(Files.readAllBytes(FIX.resolve("crlf.md")), Charsets.UTF_8)
        assertTrue("\r\n" in raw)
        assertEquals(parseItem(raw.replace("\r\n", "\n")).fm, parseItem(raw).fm)
        assertEquals(parseItem(raw.replace("\r\n", "\n")).body, parseItem(raw).body)
    }

    @Test
    fun `bad yaml raises item error`() {
        assertThrows<ItemError> { parseItem("---\nid: WI-1\ntitle: a: b: [\n---\n") }
        assertThrows<ItemError> { parseItem("no frontmatter here\n") }
    }

    @Test
    fun `missing id raises item error`() {
        assertThrows<ItemError> { parseItem("---\ntitle: T\n---\n\nbody\n") }
    }

    @Test
    fun properties() {
        val it = parseItem(wi42())
        assertEquals(listOf("WI-42", "01jb7q3m", "story", "Idempotent PaymentRequested handling"), listOf(it.id, it.uid, it.type, it.title))
    }

    @Test
    fun `file name is lowercase id and sanitised`() {
        assertEquals("wi-42 - Idempotent PaymentRequested handling.md", fileName("WI-42", "Idempotent PaymentRequested handling"))
        var n = fileName("WI-7", "a<b>:c\"/d\\e|f?g*. ")
        assertFalse(n.substring("wi-7 - ".length).any { it in "<>:\"/\\|?*" })
        assertFalse(n.dropLast(3).endsWith(".") || n.dropLast(3).endsWith(" "))
        n = fileName("WI-7", "word ".repeat(60))
        assertTrue(n.substring("wi-7 - ".length, n.length - ".md".length).cpLen() <= 60)
        assertFalse(fileName("WI-7", "x".repeat(300)).dropLast(3).endsWith(" "))
        assertTrue("🦐 Gambas" in fileName("WI-7", "🦐 Gambas"))
    }

    @Test
    fun checklists() {
        val body = parseItem(wi42()).body
        assertEquals(listOf(Check(1, false, "A duplicate message has no second effect"),
            Check(2, false, "After 3 retries the message goes to the DLQ")), checklist(body, "AC"))
        assertEquals(listOf(Check(1, false, "acceptance criteria met")), checklist(body, "DOD"))
        assertTrue(checklist(body.replace("- [ ] #1 A dup", "- [x] #1 A dup"), "AC")[0].done)
        assertEquals("As … I want … so that …", description(body))
    }

    @Test
    fun `templates per type and language`() {
        var b = newBody("story", "es", listOf("x"))
        for (marker in listOf("<!-- SECTION:DESCRIPTION:BEGIN -->", "<!-- AC:BEGIN -->", "<!-- DOD:BEGIN -->", "- [ ] #1 x")) {
            assertTrue(marker in b)
        }
        assertTrue(listOf("como", "quiero", "para").all { it in b.lowercase() })
        b = newBody("bug", "en", emptyList()).lowercase()
        assertTrue(listOf("steps", "expected", "actual", "environment").all { it in b })
        for (t in TYPES) for (lang in listOf("en", "es")) assertTrue("DESCRIPTION:END" in newBody(t, lang, emptyList()))
        assertEquals("acceptance criteria met", defaultDod("en")[0])
        assertEquals(3, defaultDod("es").size)
    }

    @Test
    fun `load dir reports problems`(@TempDir tmp: Path) {
        val d = Files.createDirectory(tmp.resolve("tasks"))
        Files.write(d.resolve("wi-1 - ok.md"), "---\nid: WI-1\ntitle: ok\n---\n\nb\n".toByteArray())
        Files.write(d.resolve("bad.md"), "---\ntitle: no id\n---\n".toByteArray())
        val (items, problems) = loadDir(d)
        assertEquals(listOf("WI-1"), items.map { it.id })
        assertEquals(d.resolve("wi-1 - ok.md"), items[0].path)
        assertEquals(1, problems.size)
        assertEquals(d.resolve("bad.md"), problems[0].path)
        assertTrue(problems[0].error.isNotEmpty())
        assertEquals(emptyList<Item>() to emptyList<Problem>(), loadDir(tmp.resolve("nope")))
    }

    @Test
    fun `new body takes a description and criteria`() {
        val b = newBody("task", "en", listOf("done"), description = "Do it.\nTwice.", criteria = listOf("a", " b  c ", " "))
        assertEquals("Do it.\nTwice.", description(b))
        assertEquals(listOf(1 to "a", 2 to "b c"), checklist(b, "AC").map { it.n to it.text })
        assertEquals(listOf("done"), checklist(b, "DOD").map { it.text })
        assertEquals(newBody("task", "en", listOf("done"), description = "  ", criteria = emptyList()), newBody("task", "en", listOf("done")))
    }

    @Test
    fun `set description and add criteria keep the rest`() {
        var b = newBody("task", "en", listOf("done"), criteria = listOf("one"))
        b = b.replace("- [ ] #1 one", "- [x] #1 one")
        val b2 = addCriteria(setDescription(b, "New."), listOf("two"))
        assertEquals("New.", description(b2))
        assertEquals(checklist(b, "DOD"), checklist(b2, "DOD"))
        assertEquals(listOf(1 to true, 2 to false), checklist(b2, "AC").map { it.n to it.done })
        assertEquals(b2, addCriteria(b2, listOf(" ")))
        val bare = "just notes\n"
        assertEquals("D", description(setDescription(bare, "D")))
        assertTrue(setDescription(bare, "D").endsWith("just notes\n"))
        assertEquals(listOf("x"), checklist(addCriteria(bare, listOf("x")), "AC").map { it.text })
        val plain = "## Definition of Done\n<!-- DOD:BEGIN -->\n- [ ] #1 d\n<!-- DOD:END -->\n"
        val out = addCriteria(plain, listOf("x"))
        assertTrue(out.indexOf("AC:BEGIN") < out.indexOf("DOD:BEGIN"))
        assertEquals("d", checklist(out, "DOD")[0].text)
    }
}
