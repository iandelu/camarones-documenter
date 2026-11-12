package camaron.kanban

import java.io.IOException
import java.nio.file.Files
import java.nio.file.Path
import java.util.regex.Pattern
import org.yaml.snakeyaml.error.YAMLException

val FIELD_ORDER = listOf("id", "title", "status", "assignee", "reporter", "created_date", "updated_date", "due_date",
    "labels", "milestone", "dependencies", "references", "documentation", "modified_files", "parent_task_id", "subtasks",
    "priority", "type", "project", "ordinal", "onStatusChange")

class ItemError(message: String, cause: Throwable? = null) : PyValueError(message, cause)

/** A Backlog.md (v1.55.3) task file: YAML frontmatter + Markdown body. */
data class Item(val fm: Map<Any?, Any?> = emptyMap(), val body: String = "", val path: Path? = null) {
    private fun field(key: String): String = if (key in fm) pyStr(fm[key]) else ""
    val id: String get() = field("id")
    val uid: String get() = field("x-uid")
    val title: String get() = field("title")
    val type: String get() = field("type")
}

data class Problem(val path: Path, val error: String)

private val FRONTMATTER = pyRegex("\\A---\\n(.*?\\n)?---[ \\t]*(?:\\n|\\z)", Pattern.DOTALL)
private val BAD = pyRegex("[/\\\\:*?\"<>|]")
private val CHECK = pyRegex("^- \\[([ xX])\\] #(\\d+) (.*)$", Pattern.MULTILINE)
private val DESCRIPTION = pyRegex("(<!-- SECTION:DESCRIPTION:BEGIN -->\\n?).*?(<!-- SECTION:DESCRIPTION:END -->)", Pattern.DOTALL)

/** A date written unquoted by hand arrives as a date; keep it as text. */
private fun plain(v: Any?): Any? = when (v) {
    is Map<*, *> -> v.entries.associateTo(LinkedHashMap<Any?, Any?>()) { it.key to plain(it.value) }
    is List<*> -> v.map(::plain)
    is PyDate -> v.date.toString()
    is PyDateTime -> String.format("%04d-%02d-%02d %02d:%02d", v.dateTime.year, v.dateTime.monthValue,
        v.dateTime.dayOfMonth, v.dateTime.hour, v.dateTime.minute)
    else -> v
}

/** A reference field as people write it: a list, or a lone value. */
fun asList(v: Any?): List<Any?> = when (v) {
    null -> emptyList()
    is String -> listOf(v)
    else -> pyIter(v)
}

fun parseItem(raw: String, path: Path? = null): Item {
    val text = raw.removePrefix("﻿").replace("\r\n", "\n")
    val m = FRONTMATTER.matcher(text)
    if (!m.lookingAt()) throw ItemError("no frontmatter")
    val loaded = try {
        PyYaml.load(m.group(1) ?: "")
    } catch (e: YAMLException) {
        throw ItemError("invalid frontmatter: ${(e.message ?: "").lineSequence().first()}", e)
    }
    val fm = loaded.takeIf(::pyTruthy) ?: emptyMap<Any?, Any?>()
    if (fm !is Map<*, *>) throw ItemError("frontmatter is not a mapping")
    if (!pyTruthy(fm["id"])) throw ItemError("missing id")
    var body = text.substring(m.end())
    if (body.startsWith("\n")) body = body.substring(1)
    @Suppress("UNCHECKED_CAST")
    return Item(plain(fm) as Map<Any?, Any?>, body, path)
}

private fun ordered(fm: Map<Any?, Any?>): Map<Any?, Any?> {
    val present = fm.filterValues { it != null }
    val known = FIELD_ORDER.filter { it in present }
    val other = present.keys.filter { (it !is String || it !in FIELD_ORDER) && !pyStr(it).startsWith("x-") }
    val xs = present.keys.filter { pyStr(it).startsWith("x-") }
    return (known + other + xs).associateWithTo(LinkedHashMap()) { present[it] }
}

fun serializeItem(item: Item): String = "---\n${PyYaml.dump(ordered(item.fm))}---\n\n${item.body}"

fun sanitizeTitle(title: String): String {
    var s = pyRStrip(pySplitWs(BAD.matcher(title).replaceAll("")).joinToString(" "), ". ")
    if (s.cpLen() > 60) {
        var cut = s.cpTake(60)
        if (s.cpAt(60) != " " && " " in cut) cut = cut.substringBeforeLast(' ')
        s = pyRStrip(cut, ". ")
    }
    return s.ifEmpty { "untitled" }
}

fun fileName(itemId: String, title: String): String = "${itemId.lowercase()} - ${sanitizeTitle(title)}.md"

private fun block(body: String, tag: String): String? {
    val m = pyRegex("<!-- ${Pattern.quote(tag)}:BEGIN -->\\n?(.*?)<!-- ${Pattern.quote(tag)}:END -->", Pattern.DOTALL)
        .matcher(body)
    return if (m.find()) m.group(1) else null
}

data class Check(val n: Int, val done: Boolean, val text: String)

fun checklist(body: String, kind: String): List<Check> {
    require(kind == "AC" || kind == "DOD") { "kind is AC or DOD" }
    val m = CHECK.matcher(block(body, kind) ?: "")
    val out = mutableListOf<Check>()
    while (m.find()) out += Check(Integer.parseInt(m.group(2)), m.group(1).lowercase() == "x", pyStrip(m.group(3)))
    return out
}

fun description(body: String): String = pyStrip(block(body, "SECTION:DESCRIPTION") ?: "")

private fun readTemplate(name: String, lang: String): String {
    val loader = Item::class.java.classLoader
    val res = loader.getResource("board/$lang/$name") ?: loader.getResource("board/en/$name")
        ?: throw IOException("no template board/en/$name")
    return res.readText(Charsets.UTF_8).replace("\r\n", "\n").replace('\r', '\n')
}

fun defaultDod(lang: String): List<String> = readTemplate("dod.txt", lang).lines().map { pyStrip(it) }.filter { it.isNotEmpty() }

private fun criteriaLines(texts: List<String>, first: Int): String =
    texts.map { pySplitWs(it).joinToString(" ") }.filter { it.isNotEmpty() }
        .withIndex().joinToString("") { (i, t) -> "- [ ] #${i + first} $t\n" }

/** Section headers and markers are Backlog.md's (English) in every language; only the prompts inside are translated. */
fun newBody(type: String, lang: String, dod: List<String>, description: String? = null, criteria: List<String> = emptyList()): String {
    val desc = pyStrip(description ?: "").ifEmpty { pyStrip(readTemplate("$type.md", lang)) }
    val checks = dod.withIndex().joinToString("") { (i, t) -> "- [ ] #${i + 1} $t\n" }
    return "## Description\n<!-- SECTION:DESCRIPTION:BEGIN -->\n" + desc + "\n<!-- SECTION:DESCRIPTION:END -->\n\n" +
        "## Acceptance Criteria\n<!-- AC:BEGIN -->\n" + criteriaLines(criteria, 1) + "<!-- AC:END -->\n\n" +
        "## Definition of Done\n<!-- DOD:BEGIN -->\n" + checks + "<!-- DOD:END -->\n"
}

/** The body with its description block replaced (a body without one gets the section first, the rest kept). */
fun setDescription(body: String, text: String): String {
    val t = pyStrip(text)
    val m = DESCRIPTION.matcher(body)
    if (m.find()) {
        return body.substring(0, m.start()) + m.group(1) + (if (t.isNotEmpty()) "$t\n" else "") + m.group(2) +
            body.substring(m.end())
    }
    return "## Description\n<!-- SECTION:DESCRIPTION:BEGIN -->\n$t\n<!-- SECTION:DESCRIPTION:END -->\n\n$body"
}

/** The body with `texts` appended to the acceptance criteria, numbered after the highest existing number. */
fun addCriteria(body: String, texts: List<String>): String {
    val lines = criteriaLines(texts, (checklist(body, "AC").map { it.n } + 0).max() + 1)
    if (lines.isEmpty()) return body
    val end = "<!-- AC:END -->"
    val i = body.indexOf(end)
    if (i >= 0) return body.substring(0, i) + lines + body.substring(i)
    val block = "## Acceptance Criteria\n<!-- AC:BEGIN -->\n$lines$end\n\n"
    val j = body.indexOf("## Definition of Done")
    if (j >= 0) return body.substring(0, j) + block + body.substring(j)
    return pyRStrip(body, "\n") + (if (pyStrip(body).isNotEmpty()) "\n\n" else "") + pyRStrip(block, "\n") + "\n"
}

private val PATH_ORDER: Comparator<Path> =
    if (IS_WIN) compareBy(PY_ORDER) { it.fileName.toString().lowercase() } else compareBy(PY_ORDER) { it.fileName.toString() }

private fun isMd(name: String): Boolean = if (IS_WIN) name.lowercase().endsWith(".md") else name.endsWith(".md")

fun loadDir(d: Path): Pair<List<Item>, List<Problem>> {
    val items = mutableListOf<Item>()
    val problems = mutableListOf<Problem>()
    if (!Files.isDirectory(d)) return items to problems
    val files = Files.list(d).use { s -> s.iterator().asSequence().filter { isMd(it.fileName.toString()) }.toList() }
    for (f in files.sortedWith(PATH_ORDER)) {
        try {
            items += parseItem(readTextPy(f), f)
        } catch (e: ItemError) {
            problems += Problem(f, e.message ?: "")
        } catch (e: IOException) {
            problems += Problem(f, e.toString())
        }
    }
    return items to problems
}
