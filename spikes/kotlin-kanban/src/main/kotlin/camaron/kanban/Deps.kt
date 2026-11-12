package camaron.kanban

/** A footprint that overlaps everything. */
const val ALL = "*"

/** The filesystem ignores case: two spellings of a path are one file. */
val FOLD: Boolean = IS_WIN || IS_MAC
private val NO_PRIORITY = PRIORITIES.size

data class Node(
    val id: String,
    val status: String = "Backlog",
    val priority: String? = null,
    val touches: List<String> = emptyList(),
    val repos: List<String> = emptyList(),
    val deps: List<String> = emptyList(),
    val archived: Boolean = false,
    val parent: String? = null,
)

/** Why an item waits: `dependency`, `missing`, `conflict`, `near` (a shared group) or `wave`. */
data class Reason(val id: String? = null, val kind: String, val files: List<String>? = null, val wave: Int? = null)

data class Waiting(val id: String, val blockedBy: List<Reason>)

class CycleError(val cycle: List<String>) : PyValueError("dependency cycle: " + cycle.joinToString(" -> "))

/** Ids of the items that are somebody's parent: a grouping, never work of its own. */
fun containers(nodes: List<Node>): Set<String> {
    val ids = nodes.mapTo(HashSet()) { it.id }
    return nodes.map { pyStrip(it.parent ?: "").uppercase() }.filterTo(LinkedHashSet()) { it in ids }
}

/** `repo:path` with `/` separators and no empty or `.` segment; `..` is refused; `fold` lower-cases the path. */
fun normTouch(ref: String, fold: Boolean): String {
    val stripped = pyStrip(ref)
    val sep = stripped.indexOf(':')
    val repo = pyStrip(if (sep < 0) stripped else stripped.substring(0, sep))
    if (sep < 0 || repo.isEmpty()) throw PyValueError("touch needs 'repo:path': ${pyRepr(ref)}")
    val path = pyStrip(stripped.substring(sep + 1)).replace('\\', '/')
    val parts = path.split('/').filter { it != "" && it != "." }
    if (".." in parts) throw PyValueError("touch may not leave its repo: ${pyRepr(ref)}")
    val norm = (if (path.startsWith("/") && parts.isNotEmpty()) "/" else "") + parts.joinToString("/")
    return "$repo:${if (fold) norm.lowercase() else norm}"
}

private fun repoOf(touch: String): String = touch.substringBefore(':')

private fun isDone(node: Node): Boolean = node.status == "Done" || node.archived

private fun rank(node: Node): Int = PRIORITIES.indexOf(node.priority).let { if (it < 0) NO_PRIORITY else it }

private val NODE_ORDER: Comparator<Node> = compareBy<Node> { rank(it) }.thenBy { idKey(it.id) }

/** The files an item touches; an agent treats an item with none as touching its repos (or everything). */
fun footprint(node: Node, agent: Boolean): Set<String> {
    val touches = LinkedHashSet(node.touches)
    if (touches.isNotEmpty() || !agent) return touches
    return node.repos.mapTo(LinkedHashSet()) { "$it:*" }.ifEmpty { linkedSetOf(ALL) }
}

private fun same(x: String, y: String, fold: Boolean): Boolean {
    if (x == y) return true
    if (!fold) return false
    return repoOf(x) == repoOf(y) && x.substringAfter(':', "").lowercase() == y.substringAfter(':', "").lowercase()
}

/** Entries the two footprints share; `ALL` meets everything, `repo:*` every entry of that repo. */
fun overlap(a: Set<String>, b: Set<String>, fold: Boolean? = null): Set<String> {
    val f = fold ?: FOLD
    val shared = LinkedHashSet<String>()
    for (x in a) {
        for (y in b) {
            when {
                same(x, y, f) -> shared += x
                x == ALL -> shared += y
                y == ALL -> shared += x
                repoOf(x) == repoOf(y) -> when {
                    x.endsWith(":*") -> shared += y
                    y.endsWith(":*") -> shared += x
                }
            }
        }
    }
    return shared
}

/** Task dependencies from "file uses file" edges and from the code a docs-only task's pages cite. */
fun order(tasks: Map<String, List<String>>, edges: Set<Pair<String, String>>, cites: Map<String, Set<String>>): Map<String, List<String>> {
    val owners = HashMap<String, MutableSet<String>>()
    for ((tid, files) in tasks) for (f in files) owners.getOrPut(f) { HashSet() } += tid
    val deps = tasks.keys.associateWithTo(LinkedHashMap()) { HashSet<String>() }
    for ((src, dst) in edges) for (b in owners[src].orEmpty()) deps.getValue(b) += owners[dst].orEmpty()
    for ((tid, files) in tasks) {
        if (files.isNotEmpty() && files.all { it.startsWith("cam-docs:") }) {
            for (page in files) for (code in cites[page].orEmpty()) deps.getValue(tid) += owners[code].orEmpty()
        }
    }
    return deps.entries.sortedWith(compareBy { idKey(it.key) })
        .associateTo(LinkedHashMap()) { (tid, d) -> tid to (d - tid).sortedWith(ID_ORDER) }
}

/** Strongly connected components with two or more members (iterative Tarjan), each sorted, the list sorted. */
fun sccs(graph: Map<String, List<String>>): List<List<String>> {
    val nodes = (graph.keys + graph.values.flatten()).toSet().sortedWith(ID_ORDER)
    val succ = nodes.associateWith { v -> graph[v].orEmpty().toSet().sortedWith(ID_ORDER) }
    val index = HashMap<String, Int>()
    val low = HashMap<String, Int>()
    val onStack = HashSet<String>()
    val stack = ArrayDeque<String>()
    val found = mutableListOf<List<String>>()
    var counter = 0
    fun open(v: String) {
        index[v] = counter
        low[v] = counter
        counter++
        stack.addLast(v)
        onStack += v
    }
    for (root in nodes) {
        if (root in index) continue
        open(root)
        val work = ArrayDeque<Pair<String, Iterator<String>>>()
        work.addLast(root to succ.getValue(root).iterator())
        while (work.isNotEmpty()) {
            val (v, it) = work.last()
            var descended = false
            while (it.hasNext()) {
                val w = it.next()
                if (w !in index) {
                    open(w)
                    work.addLast(w to succ.getValue(w).iterator())
                    descended = true
                    break
                }
                if (w in onStack) low[v] = minOf(low.getValue(v), index.getValue(w))
            }
            if (descended) continue
            work.removeLast()
            if (work.isNotEmpty()) {
                val parent = work.last().first
                low[parent] = minOf(low.getValue(parent), low.getValue(v))
            }
            if (low[v] == index[v]) {
                val comp = mutableListOf<String>()
                do {
                    val w = stack.removeLast()
                    onStack -= w
                    comp += w
                } while (w != v)
                if (comp.size > 1) found += comp.sortedWith(ID_ORDER)
            }
        }
    }
    return found.sortedWith(compareBy { idKey(it[0]) })
}

/** Open items sharing a file with `node` (`conflict`) or, given `groups` (file -> group), only a group (`near`). */
fun conflicts(node: Node, others: List<Node>, groups: Map<String, String>? = null): List<Reason> {
    val mine = node.touches.toSet()
    val myGroups = if (!groups.isNullOrEmpty()) mine.mapNotNullTo(HashSet()) { groups[it] } else emptySet()
    val found = mutableListOf<Reason>()
    for (other in others.sortedWith(compareBy { idKey(it.id) })) {
        if (other.id == node.id || isDone(other)) continue
        val theirs = other.touches.toSet()
        val shared = overlap(mine, theirs)
        if (shared.isNotEmpty()) {
            found += Reason(other.id, "conflict", shared.sortedWith(PY_ORDER))
        } else if (!groups.isNullOrEmpty()) {
            val close = theirs.filter { groups[it] in myGroups }.sortedWith(PY_ORDER)
            if (close.isNotEmpty()) found += Reason(other.id, "near", close)
        }
    }
    return found
}

/** Groups of items that can run in parallel: topological levels, then first-fit waves without file clashes. */
fun waves(nodes: List<Node>, agent: Boolean = true): List<List<String>> {
    val grouping = containers(nodes)
    val byId = LinkedHashMap<String, Node>()
    for (n in nodes) if (n.id !in grouping) byId[n.id] = n
    val deps = byId.mapValuesTo(LinkedHashMap()) { (i, n) ->
        n.deps.filter { it in byId && it != i }.toSet().sortedWith(ID_ORDER)
    }
    sccs(deps).firstOrNull()?.let { throw CycleError(it) }
    val level = HashMap<String, Int>()
    var pending: Map<String, List<String>> = deps
    while (pending.isNotEmpty()) {
        for (i in pending.keys.sortedWith(ID_ORDER)) {
            if (deps.getValue(i).all { it in level }) {
                level[i] = 1 + (deps.getValue(i).maxOfOrNull { level.getValue(it) } ?: -1)
            }
        }
        pending = pending.filterKeys { it !in level }
    }
    val placed = mutableListOf<MutableList<String>>()
    val prints = mutableListOf<MutableList<Set<String>>>()
    val waveOf = HashMap<String, Int>()
    val placement = compareBy<String> { level.getValue(it) }.thenBy { rank(byId.getValue(it)) }.thenBy { idKey(it) }
    for (i in byId.keys.sortedWith(placement)) {
        val fp = footprint(byId.getValue(i), agent)
        var w = deps.getValue(i).maxOfOrNull { waveOf.getValue(it) + 1 } ?: 0
        while (w < placed.size && prints[w].any { overlap(fp, it).isNotEmpty() }) w++
        if (w == placed.size) {
            placed += mutableListOf<String>()
            prints += mutableListOf<Set<String>>()
        }
        placed[w] += i
        prints[w] += fp
        waveOf[i] = w
    }
    return placed.map { wave -> wave.sortedWith(compareBy(NODE_ORDER) { byId.getValue(it) }) }
}

/** Why `node` cannot start now: dependencies not Done (or unknown) and In Progress items sharing its files. */
fun blockedBy(node: Node, board: List<Node>, agent: Boolean, grouping: Set<String>? = null,
              byId: Map<String, Node>? = null): List<Reason> {
    val index = byId ?: LinkedHashMap<String, Node>().apply { board.forEach { put(it.id, it) } }
    val groups = grouping ?: containers(board)
    val reasons = mutableListOf<Reason>()
    for (d in (node.deps.toSet() - node.id).sortedWith(ID_ORDER)) {
        val dep = index[d]
        if (dep == null) reasons += Reason(d, "missing")
        else if (!isDone(dep)) reasons += Reason(d, "dependency")
    }
    if (node.id in groups) return reasons
    val mine = footprint(node, agent)
    for (other in board.sortedWith(compareBy { idKey(it.id) })) {
        if (other.id == node.id || other.id in groups || other.status != "In Progress" || other.archived) continue
        val shared = overlap(mine, footprint(other, agent))
        if (shared.isNotEmpty()) reasons += Reason(other.id, "conflict", shared.sortedWith(PY_ORDER))
    }
    return reasons
}

/** Backlog/Ready items that can start now and never collide with each other: the first wave the start gate lets
 * through, at most `n`. Every other candidate lands in `waiting` with its reasons. */
fun ready(board: List<Node>, agent: Boolean = true, among: Set<String>? = null, n: Int? = null,
          waiting: MutableList<Waiting>? = null): List<String> {
    val grouping = containers(board)
    val byId = LinkedHashMap<String, Node>().apply { board.forEach { put(it.id, it) } }
    val free = mutableListOf<Node>()
    val held = mutableListOf<Waiting>()
    for (x in board.sortedWith(compareBy { idKey(it.id) })) {
        if (x.status !in setOf("Backlog", "Ready") || x.archived || x.id in grouping || (among != null && x.id !in among)) {
            continue
        }
        val why = blockedBy(x, board, agent, grouping, byId)
        if (why.isNotEmpty()) held += Waiting(x.id, why) else free += x.copy(deps = emptyList())
    }
    val placed = waves(free, agent)
    placed.withIndex().drop(1).forEach { (k, wave) -> wave.forEach { held += Waiting(it, listOf(Reason(kind = "wave", wave = k))) } }
    waiting?.addAll(held.sortedWith(compareBy { idKey(it.id) }))
    val first = placed.firstOrNull() ?: emptyList()
    return if (n == null) first else first.take(maxOf(n, 0))
}
