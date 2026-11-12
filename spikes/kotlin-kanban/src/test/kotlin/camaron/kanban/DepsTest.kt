package camaron.kanban

import kotlin.random.Random
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

private fun node(id: String, status: String = "Backlog", priority: String? = null, touches: List<String> = emptyList(),
                 repos: List<String> = emptyList(), deps: List<String> = emptyList(), archived: Boolean = false,
                 parent: String? = null) = Node(id, status, priority, touches, repos, deps, archived, parent)

private fun conflict(id: String, vararg files: String) = Reason(id, "conflict", files.toList())
private fun wave(k: Int) = listOf(Reason(kind = "wave", wave = k))

class DepsTest {
    @Test
    fun `norm touch`() {
        assertEquals("api:src/A.java", normTouch(" api:.\\src\\A.java ", fold = false))
        assertEquals("api:src/a.java", normTouch("api:./src/A.java", fold = true))
        assertEquals("API:src/a.java", normTouch("API:src/A.java", fold = true))
        assertThrows<PyValueError> { normTouch("api:../x", fold = false) }
        assertThrows<PyValueError> { normTouch("api:a\\..\\b", fold = false) }
        assertThrows<PyValueError> { normTouch("no-repo-part", fold = false) }
    }

    @Test
    fun `order provider first`() {
        val tasks = mapOf("T1" to listOf("api:a.py"), "T2" to listOf("api:b.py"))
        assertEquals(mapOf("T1" to emptyList(), "T2" to listOf("T1")), order(tasks, setOf("api:b.py" to "api:a.py"), emptyMap()))
    }

    @Test
    fun `order ignores self loops and sorts by id key`() {
        val tasks = mapOf("WI-10" to listOf("api:a.py"), "WI-2" to listOf("api:b.py"), "WI-3" to listOf("api:c.py", "api:d.py"))
        val edges = setOf("api:c.py" to "api:d.py", "api:c.py" to "api:a.py", "api:c.py" to "api:b.py")
        val got = order(tasks, edges, emptyMap())
        assertEquals(mapOf("WI-10" to emptyList(), "WI-2" to emptyList(), "WI-3" to listOf("WI-2", "WI-10")), got)
        assertEquals(listOf("WI-2", "WI-3", "WI-10"), got.keys.toList())
    }

    @Test
    fun `docs after code`() {
        val tasks = mapOf("T1" to listOf("api:a.py"), "T2" to listOf("cam-docs:docs/x.md"), "T3" to listOf("api:z.py", "cam-docs:docs/y.md"))
        val cites = mapOf("cam-docs:docs/x.md" to setOf("api:a.py"), "cam-docs:docs/y.md" to setOf("api:a.py"))
        val got = order(tasks, emptySet(), cites)
        assertEquals(listOf("T1"), got["T2"])
        assertEquals(emptyList<String>(), got["T3"])
        assertEquals(emptyList<String>(), got["T1"])
    }

    @Test
    fun `sccs finds two way groups`() {
        assertEquals(listOf(listOf("A", "B")), sccs(mapOf("A" to listOf("B"), "B" to listOf("A"), "C" to emptyList())))
        assertEquals(emptyList<List<String>>(), sccs(mapOf("A" to listOf("A"), "B" to emptyList())))
        val chain = (1 until 5000).associate { "WI-$it" to listOf("WI-${it + 1}") } + ("WI-5000" to listOf("WI-1"))
        assertEquals(listOf(chain.keys.sortedBy { it.substring(3).toInt() }), sccs(chain))
        val two = mapOf("WI-9" to listOf("WI-10"), "WI-10" to listOf("WI-9"), "WI-2" to listOf("WI-3"), "WI-3" to listOf("WI-2", "WI-9"))
        assertEquals(listOf(listOf("WI-2", "WI-3"), listOf("WI-9", "WI-10")), sccs(two))
    }

    @Test
    fun `conflict and near`() {
        val me = node("WI-1", touches = listOf("api:a.py", "api:b.py"))
        val shared = node("WI-2", status = "In Progress", touches = listOf("api:b.py", "api:z.py"))
        val sameGroup = node("WI-3", touches = listOf("api:c.py"))
        val otherGroup = node("WI-4", touches = listOf("web:q.js"))
        val done = node("WI-5", status = "Done", touches = listOf("api:a.py"))
        val archived = node("WI-6", touches = listOf("api:a.py"), archived = true)
        val groups = mapOf("api:a.py" to "g1", "api:b.py" to "g1", "api:c.py" to "g1", "api:z.py" to "g2", "web:q.js" to "g3")
        val others = listOf(otherGroup, sameGroup, shared, done, archived, me)
        assertEquals(listOf(conflict("WI-2", "api:b.py")), conflicts(me, others))
        assertEquals(listOf(conflict("WI-2", "api:b.py"), Reason("WI-3", "near", listOf("api:c.py"))), conflicts(me, others, groups))
    }

    @Test
    fun `unknown footprint is whole repo for agents`() {
        val unknown = node("WI-1", repos = listOf("api"))
        assertEquals(setOf("api:*"), footprint(unknown, agent = true))
        assertEquals(emptySet<String>(), footprint(unknown, agent = false))
        assertEquals(setOf(ALL), footprint(node("WI-2"), agent = true))
        assertEquals(setOf("api:a.py"), footprint(node("WI-3", touches = listOf("api:a.py"), repos = listOf("web")), agent = true))
        assertEquals(setOf("api:src/A.java"), overlap(footprint(unknown, agent = true), setOf("api:src/A.java")))
        assertEquals(emptySet<String>(), overlap(footprint(unknown, agent = true), setOf("web:a.js")))
        assertEquals(emptySet<String>(), overlap(footprint(unknown, agent = false), setOf("api:src/A.java")))
        assertEquals(setOf("web:a.js", "api:b.py"), overlap(setOf(ALL), setOf("web:a.js", "api:b.py")))
        assertEquals(setOf("api:a.py"), overlap(setOf("api:a.py"), setOf("api:a.py", "api:b.py")))
        assertEquals(emptySet<String>(), overlap(emptySet(), setOf(ALL)))
    }

    private val golden = listOf(
        node("WI-2", priority = "P0", touches = listOf("api:a.py")),
        node("WI-3", priority = "P2", touches = listOf("api:b.py"), deps = listOf("WI-2")),
        node("WI-4", priority = null, touches = listOf("api:c.py"), deps = listOf("WI-3")),
        node("WI-5", priority = "P1", touches = listOf("api:a.py")),
        node("WI-6", priority = "P0", touches = listOf("web:x.js"), deps = listOf("WI-5", "WI-99")),
        node("WI-7", priority = "P2", touches = listOf("api:d.py")),
    )

    @Test
    fun `waves golden`() {
        val expected = listOf(listOf("WI-2", "WI-7"), listOf("WI-5", "WI-3"), listOf("WI-6", "WI-4"))
        assertEquals(expected, waves(golden))
        assertEquals(expected, waves(golden))
        for (seed in 0 until 5) assertEquals(expected, waves(golden.shuffled(Random(seed))))
    }

    @Test
    fun `waves unknown footprint is conservative`() {
        val nodes = listOf(node("WI-1", touches = listOf("api:a.py")), node("WI-2", repos = listOf("api")), node("WI-3", touches = listOf("web:b.js")))
        assertEquals(listOf(listOf("WI-1", "WI-3"), listOf("WI-2")), waves(nodes))
        assertEquals(listOf(listOf("WI-1"), listOf("WI-2")), waves(listOf(node("WI-1"), node("WI-2", touches = listOf("web:b.js")))))
        assertEquals(emptyList<List<String>>(), waves(emptyList()))
    }

    @Test
    fun `waves cycle raises`() {
        val err = assertThrows<CycleError> { waves(listOf(node("WI-2", deps = listOf("WI-1")), node("WI-1", deps = listOf("WI-2")), node("WI-3"))) }
        assertEquals(listOf("WI-1", "WI-2"), err.cycle)
    }

    @Test
    fun `blocked by and ready`() {
        val board = listOf(
            node("WI-1", status = "Done", touches = listOf("api:a.py")),
            node("WI-2", archived = true, touches = listOf("api:old.py")),
            node("WI-3", status = "In Progress", touches = listOf("api:b.py", "api:c.py")),
            node("WI-4", status = "Ready", priority = "P2", touches = listOf("api:a.py"), deps = listOf("WI-1", "WI-2")),
            node("WI-5", status = "Ready", priority = "P1", touches = listOf("api:b.py")),
            node("WI-6", priority = "P0", touches = listOf("web:x.js"), deps = listOf("WI-3")),
            node("WI-7", priority = "P1", touches = listOf("web:x.js"), deps = listOf("WI-404")),
            node("WI-8", status = "Ready", priority = "P0", touches = listOf("web:x.js")),
            node("WI-9", status = "Ready", priority = "P3", touches = listOf("web:y.js")),
            node("WI-10", status = "Ready", priority = "P3", touches = listOf("api:e.py")),
            node("WI-11", status = "In Review", touches = listOf("api:f.py")),
        )
        val by = board.associateBy { it.id }
        assertEquals(emptyList<Reason>(), blockedBy(by.getValue("WI-4"), board, agent = true))
        assertEquals(listOf(conflict("WI-3", "api:b.py")), blockedBy(by.getValue("WI-5"), board, agent = true))
        assertEquals(listOf(Reason("WI-3", "dependency")), blockedBy(by.getValue("WI-6"), board, agent = true))
        assertEquals(listOf(Reason("WI-404", "missing")), blockedBy(by.getValue("WI-7"), board, agent = true))
        val wide = node("WI-12", status = "Ready", repos = listOf("api"))
        assertEquals(listOf(conflict("WI-3", "api:b.py", "api:c.py")), blockedBy(wide, board, agent = true))
        assertEquals(emptyList<Reason>(), blockedBy(wide, board, agent = false))
        assertEquals(listOf("WI-8", "WI-4", "WI-9", "WI-10"), ready(board))
    }

    @Test
    fun `ready orders by wave then priority then id`() {
        val board = listOf(
            node("WI-1", status = "Ready", priority = "P3", touches = listOf("api:a.py")),
            node("WI-2", status = "Ready", priority = "P0", touches = listOf("api:a.py")),
            node("WI-3", priority = "P2", touches = listOf("web:b.js")),
            node("WI-4", status = "Ready", touches = listOf("web:c.js")),
            node("WI-5", status = "Ready", priority = "P2", touches = listOf("web:d.js")),
        )
        val waiting = mutableListOf<Waiting>()
        assertEquals(listOf("WI-2", "WI-3", "WI-5", "WI-4"), ready(board, waiting = waiting))
        assertEquals(listOf(Waiting("WI-1", wave(1))), waiting)
        assertEquals(listOf("WI-2", "WI-3"), ready(board, n = 2))
        assertEquals(emptyList<String>(), ready(board, n = 0))
    }

    @Test
    fun `ready never hands out two tasks on the same file`() {
        val board = listOf(node("WI-1", touches = listOf("api:a.py")), node("WI-2", touches = listOf("api:a.py")),
            node("WI-3", touches = listOf("api:a.py")), node("WI-4", status = "In Progress", touches = listOf("web:x.js")),
            node("WI-5", touches = listOf("web:x.js")))
        var waiting = mutableListOf<Waiting>()
        assertEquals(listOf("WI-1"), ready(board, waiting = waiting))
        assertEquals(listOf(Waiting("WI-2", wave(1)), Waiting("WI-3", wave(2)), Waiting("WI-5", listOf(conflict("WI-4", "web:x.js")))), waiting)
        waiting = mutableListOf()
        assertEquals(listOf("WI-2"), ready(board, among = setOf("WI-2", "WI-3"), waiting = waiting))
        assertEquals(listOf("WI-3"), waiting.map { it.id })
    }

    @Test
    fun `ready people view uses people footprints`() {
        val board = listOf(node("WI-1", repos = listOf("api")), node("WI-2", repos = listOf("api")), node("WI-3", touches = listOf("api:a.py")))
        assertEquals(listOf("WI-1"), ready(board))
        assertEquals(listOf("WI-1", "WI-2", "WI-3"), ready(board, agent = false))
        assertEquals(listOf(listOf("WI-1", "WI-2", "WI-3")), waves(board, agent = false))
        assertEquals(listOf(listOf("WI-1"), listOf("WI-2"), listOf("WI-3")), waves(board))
    }

    @Test
    fun `a node listing itself is never blocked by itself`() {
        val me = node("WI-1", status = "Ready", touches = listOf("api:a.py"), deps = listOf("WI-1"))
        assertEquals(emptyList<Reason>(), blockedBy(me, listOf(me), agent = true))
        assertEquals(listOf("WI-1"), ready(listOf(me)))
    }

    @Test
    fun `containers are the items with children`() {
        val nodes = listOf(node("WI-1"), node("WI-2", parent = "WI-1"), node("WI-3", archived = true, parent = "wi-4"), node("WI-4"), node("WI-5"))
        assertEquals(setOf("WI-1", "WI-4"), containers(nodes))
        assertEquals(emptySet<String>(), containers(listOf(node("WI-1"))))
    }

    @Test
    fun `containers never block never wait for conflicts and are never candidates`() {
        val board = mutableListOf(
            node("WI-1", status = "In Progress", touches = listOf("api:a.py")),
            node("WI-2", status = "Ready", touches = listOf("api:a.py"), parent = "WI-1"),
            node("WI-3", status = "Ready", repos = listOf("api"), parent = "WI-1"),
            node("WI-4", status = "Ready", repos = listOf("api"), deps = listOf("WI-9")),
            node("WI-9", touches = listOf("web:z.js")),
        )
        val by = board.associateBy { it.id }
        assertEquals(emptyList<Reason>(), blockedBy(by.getValue("WI-2"), board, agent = true))
        assertEquals(emptyList<Reason>(), blockedBy(by.getValue("WI-3"), board, agent = true))
        assertEquals(listOf(Reason("WI-9", "dependency")), blockedBy(by.getValue("WI-4"), board, agent = true))
        assertEquals(emptyList<Reason>(), blockedBy(by.getValue("WI-1"), board, agent = true))
        board[0] = board[0].copy(deps = listOf("WI-9"))
        assertEquals(listOf(Reason("WI-9", "dependency")), blockedBy(board[0], board, agent = true))
        assertEquals(listOf("WI-2", "WI-9"), ready(board))
        val waiting = mutableListOf<Waiting>()
        ready(board, waiting = waiting)
        assertEquals(listOf(Waiting("WI-3", wave(1)), Waiting("WI-4", listOf(Reason("WI-9", "dependency")))), waiting)
        assertEquals(listOf(listOf("WI-2", "WI-9"), listOf("WI-3"), listOf("WI-4")), waves(board))
    }

    @Test
    fun `norm touch collapses empty and dot segments`() {
        assertEquals("api:src/A.java", normTouch("api:src//A.java", fold = false))
        assertEquals("api:src/main/A.java", normTouch("api:src/./main/./A.java", fold = false))
        assertEquals("api:src/main", normTouch("api:src/main/", fold = false))
        assertEquals("api:src/A.java", normTouch("api:.//src\\A.java", fold = false))
        assertEquals("api:", normTouch("api:./", fold = false))
        assertThrows<PyValueError> { normTouch("api:src//../x", fold = false) }
    }

    @Test
    fun `overlap folds case where the filesystem does`() {
        assertEquals(setOf("api:src/A.java"), overlap(setOf("api:src/A.java"), setOf("api:src/a.java"), fold = true))
        assertEquals(emptySet<String>(), overlap(setOf("api:src/A.java"), setOf("api:src/a.java"), fold = false))
        assertEquals(emptySet<String>(), overlap(setOf("API:a.py"), setOf("api:a.py"), fold = true))
        assertEquals(setOf("api:B.py"), overlap(setOf("api:*"), setOf("api:B.py"), fold = true))
        val expected = if (IS_WIN || IS_MAC) setOf("api:src/A.java") else emptySet()
        assertEquals(expected, overlap(setOf("api:src/A.java"), setOf("api:src/a.java")))
    }
}
