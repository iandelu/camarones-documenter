package camaron.kanban

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.io.TempDir

private fun mcard(uid: String = "aaaaaaaa", status: String = "Ready", ordinal: Long = 1000, assignee: List<String> = emptyList(),
                  t: Map<String, String> = emptyMap()) = card(uid, status, ordinal, assignee, t)

private data class Merged(val cards: Map<String, Card>, val log: List<String>, val text: String)

private fun merged(base: Map<String, Card>, ours: Map<String, Card>, theirs: Map<String, Card>): Merged {
    val (text, log) = mergeBoards(dumpBoard(base), dumpBoard(ours), dumpBoard(theirs))
    return Merged(loadBoard(text), log, text)
}

private fun write(p: Path, text: String) = Files.write(p, text.toByteArray(Charsets.UTF_8))
private fun read(p: Path) = String(Files.readAllBytes(p), Charsets.UTF_8)

class MergeTest {
    @Test
    fun `change on one side wins`() {
        val base = mapOf("WI-1" to mcard())
        val ours = mapOf("WI-1" to mcard(status = "In Progress", t = mapOf("status" to "2026-10-24T10:00:00Z ana")))
        val out = merged(base, ours, base).cards.getValue("WI-1")
        assertEquals("In Progress", out.status)
        assertEquals("2026-10-24T10:00:00Z ana", out.t["status"])
    }

    @Test
    fun `both sides latest stamp wins per field`() {
        val base = mapOf("WI-1" to mcard())
        val ours = mapOf("WI-1" to mcard(status = "In Progress", t = mapOf("status" to "2026-10-24T10:00:00Z ana")))
        val theirs = mapOf("WI-1" to mcard(status = "Done", assignee = listOf("luis"),
            t = mapOf("status" to "2026-10-24T11:00:00Z luis", "assignee" to "2026-10-24T09:00:00Z luis")))
        val out = merged(base, ours, theirs).cards.getValue("WI-1")
        assertEquals("Done", out.status)
        assertEquals(listOf("luis"), out.assignee)
        assertEquals("2026-10-24T11:00:00Z luis", out.t["status"])
    }

    @Test
    fun `tie is deterministic`() {
        val base = mapOf("WI-1" to mcard())
        val a = mapOf("WI-1" to mcard(status = "In Progress", t = mapOf("status" to "2026-10-24T10:00:00Z ana")))
        val b = mapOf("WI-1" to mcard(status = "Done", t = mapOf("status" to "2026-10-24T10:00:00Z luis")))
        val one = merged(base, a, b)
        assertEquals(one.text, merged(base, b, a).text)
        assertEquals("Done", one.cards.getValue("WI-1").status)
        val c = mapOf("WI-1" to mcard(status = "Blocked", t = mapOf("status" to "2026-10-24T10:00:00Z ana")))
        assertEquals(merged(base, a, c).text, merged(base, c, a).text)
        assertEquals("In Progress", merged(base, a, c).cards.getValue("WI-1").status)
    }

    @Test
    fun `same id added on both sides keeps both`() {
        val old = mcard("aaaaaaaa", t = mapOf("status" to "2026-10-24T09:00:00Z ana"))
        val new = mcard("bbbbbbbb", t = mapOf("status" to "2026-10-24T10:00:00Z luis"))
        val m = merged(emptyMap(), mapOf("WI-5" to new), mapOf("WI-5" to old))
        assertEquals("aaaaaaaa", m.cards.getValue("WI-5").uid)
        assertEquals("bbbbbbbb", m.cards.getValue("WI-5~bbbbbbbb").uid)
        assertTrue(m.log.isNotEmpty())
        assertEquals(m.text, merged(emptyMap(), mapOf("WI-5" to old), mapOf("WI-5" to new)).text)
    }

    @Test
    fun `delete vs change keeps the change`() {
        val base = mapOf("WI-1" to mcard("11111111"), "WI-2" to mcard("22222222"))
        val ours = mapOf("WI-1" to mcard("11111111"))
        val theirs = mapOf("WI-1" to mcard("11111111"), "WI-2" to mcard("22222222", status = "Done", t = mapOf("status" to "2026-10-24T10:00:00Z luis")))
        val m = merged(base, ours, theirs)
        assertEquals("Done", m.cards.getValue("WI-2").status)
        assertTrue(m.log.any { "WI-2" in it })
    }

    @Test
    fun `delete of an unchanged card is honoured`() {
        val base = mapOf("WI-1" to mcard("11111111"), "WI-2" to mcard("22222222"))
        assertEquals(listOf("WI-1"), merged(base, mapOf("WI-1" to mcard("11111111")), base).cards.keys.toList())
    }

    @Test
    fun `unparsable side raises and driver leaves ours`(@TempDir tmp: Path) {
        val good = dumpBoard(mapOf("WI-1" to mcard()))
        for (bad in listOf("<<<<<<< ours\nversion: 1\n", "version: 1\ncards:\n  WI-1: {uid: a, status: S, ordinal: 1, t: 5}\n")) {
            assertThrows<IllegalArgumentException> { mergeBoards(good, bad, good) }
            val (b, o, t) = listOf("b", "o", "t").map { tmp.resolve(it) }
            write(b, good)
            write(o, bad)
            write(t, good)
            assertEquals(1, driver(b, o, t))
            assertEquals(bad, read(o))
        }
    }

    @Test
    fun `driver writes ours and accepts empty base`(@TempDir tmp: Path) {
        val (b, o, t) = listOf("b", "o", "t").map { tmp.resolve(it) }
        write(b, "")
        write(o, dumpBoard(mapOf("WI-1" to mcard())))
        write(t, dumpBoard(mapOf("WI-2" to mcard("22222222"))))
        assertEquals(0, driver(b, o, t))
        assertEquals(listOf("WI-1", "WI-2"), loadBoard(read(o)).keys.toList())
    }

    @Test
    fun `driver command quotes spaces`() {
        val cmd = driverCommand(listOf("C:/Users/Ana María/uv.exe", "run", "--quiet", "--script", "C:/kit dir/camarones.py"))
        assertEquals("\"C:/Users/Ana María/uv.exe\" \"run\" \"--quiet\" \"--script\" \"C:/kit dir/camarones.py\" board merge-driver %O %A %B", cmd)
        assertTrue(driverCommand(listOf("C:\\kit dir\\x.exe")).startsWith("\"C:/kit dir/x.exe\""))
    }

    @Test
    fun `real git merge uses the driver`(@TempDir tmp: Path) {
        val repo = Files.createDirectories(tmp.resolve("repo").resolve("backlog")).parent
        fun git(vararg args: String): String {
            val p = ProcessBuilder(listOf("git") + args).directory(repo.toFile()).redirectErrorStream(true).start()
            val out = p.inputStream.readBytes().toString(Charsets.UTF_8)
            assertEquals(0, p.waitFor(), "git ${args.joinToString(" ")}: $out")
            return out
        }
        val java = Paths.get(System.getProperty("java.home"), "bin", if (IS_WIN) "java.exe" else "java").toString()
        val launcher = listOf(java, "-cp", System.getProperty("java.class.path"), "camaron.kanban.MergeDriverMain")
        git("init", "-q")
        git("checkout", "-qb", "main")
        git("config", "user.name", "Test")
        git("config", "user.email", "test@example.com")
        git("config", "merge.camaron-board.name", "Camarón board (per card)")
        git("config", "merge.camaron-board.driver", driverCommand(launcher))
        write(repo.resolve(".gitattributes"), "backlog/board.yaml merge=camaron-board\n")
        val board = repo.resolve("backlog/board.yaml")
        val base = mapOf("WI-1" to mcard("11111111"), "WI-2" to mcard("22222222", ordinal = 2000), "WI-3" to mcard("33333333", ordinal = 3000))
        write(board, dumpBoard(base))
        git("add", ".")
        git("commit", "-qm", "base")
        git("checkout", "-qb", "other")
        write(board, dumpBoard(base + ("WI-2" to mcard("22222222", "Done", 2000, t = mapOf("status" to "2026-10-24T10:00:00Z luis")))))
        git("commit", "-qam", "luis")
        git("checkout", "-q", "main")
        write(board, dumpBoard(base + ("WI-1" to mcard("11111111", "In Progress", 1000, t = mapOf("status" to "2026-10-24T09:00:00Z ana")))))
        git("commit", "-qam", "ana")
        val started = System.nanoTime()
        git("merge", "-q", "other", "-m", "merge")
        System.err.println("git merge with the JVM driver: ${(System.nanoTime() - started) / 1_000_000} ms")
        val out = loadBoard(read(board))
        assertEquals("In Progress", out.getValue("WI-1").status)
        assertEquals("Done", out.getValue("WI-2").status)
    }
}
