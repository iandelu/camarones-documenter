"""Data schemas from code (S10), no AI: SQL tables from migrations (Flyway, Liquibase), schema files and entity classes
(JPA, SQLAlchemy, Django, TypeORM, Prisma), and NoSQL collections (Mongo documents and Mongoose schemas, Firestore
collections from code and security rules), each field with its type, key and reference. Each repo gets
docs/data/<repo>.md, an AI draft whose ER diagram is a generated block (`schema`): refreshed from the code, kept when a
person edits it, and never written into a page someone else owns."""
from __future__ import annotations

import pytest

V1 = """-- init
CREATE TABLE IF NOT EXISTS owners (
  id INTEGER PRIMARY KEY,
  first_name VARCHAR(30) NOT NULL,
  city VARCHAR(80)
);
CREATE TABLE pets (
  id INT NOT NULL,
  name VARCHAR(30),
  owner_id INT REFERENCES owners(id),
  PRIMARY KEY (id)
);
"""
V2 = """CREATE TABLE `visits` (`id` int NOT NULL AUTO_INCREMENT, `pet_id` int, `visit_date` date, PRIMARY KEY (`id`));
ALTER TABLE visits ADD CONSTRAINT fk_visits_pets FOREIGN KEY (pet_id) REFERENCES pets (id);
ALTER TABLE pets ADD COLUMN birth_date DATE;
"""
VET = """package demo;

import jakarta.persistence.*;

@Entity
@Table(name = "vets")
public class Vet {
    @Id
    @GeneratedValue
    private Long id;

    @Column(name = "first_name")
    private String firstName;

    @ManyToOne
    @JoinColumn(name = "clinic_id")
    private Clinic clinic;
}
"""
RULES = """rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read: if request.auth != null;
      match /orders/{orderId} {
        allow read, write: if request.auth.uid == userId;
      }
    }
    match /sessions/{sessionId} {
      allow read: if true;
    }
  }
}
"""
FIRESTORE_TS = """import { addDoc, collection, doc, setDoc } from 'firebase/firestore';

export async function order(db, uid) {
  await addDoc(collection(db, 'users', uid, 'orders'), { total: 10, status: 'new', createdAt: Date.now() });
  await setDoc(doc(db, 'sessions', 's1'), { djName: 'x', startedAt: 1 });
}
"""


@pytest.fixture
def repos(kit):
    mig = kit.ws / "api" / "src" / "main" / "resources" / "db" / "migration"
    mig.mkdir(parents=True)
    (mig / "V1__init.sql").write_text(V1, encoding="utf-8")
    (mig / "V2__visits.sql").write_text(V2, encoding="utf-8")
    java = kit.ws / "api" / "src" / "main" / "java" / "demo"
    java.mkdir(parents=True, exist_ok=True)
    (java / "Vet.java").write_text(VET, encoding="utf-8")
    (kit.ws / "web" / "firestore.rules").write_text(RULES, encoding="utf-8")
    (kit.ws / "web" / "src" / "orders.ts").write_text(FIRESTORE_TS, encoding="utf-8")
    from lib import schemas
    return schemas


def entities(schemas, repo):
    return {e["name"]: e for s in schemas.scan()[repo]["stores"] for e in s["entities"]}


def field(e, name):
    return next(f for f in e["fields"] if f["name"] == name)


def test_sql_tables_from_migrations_in_version_order(repos):
    es = entities(repos, "api")
    assert set(es) >= {"owners", "pets", "visits"}
    assert field(es["owners"], "id")["pk"] and field(es["owners"], "first_name")["type"] == "VARCHAR(30)"
    assert field(es["owners"], "first_name")["null"] is False
    assert field(es["pets"], "id")["pk"] and field(es["pets"], "owner_id")["ref"] == "owners.id"
    assert field(es["visits"], "pet_id")["ref"] == "pets.id"                      # from ALTER TABLE … FOREIGN KEY
    assert "birth_date" in {f["name"] for f in es["pets"]["fields"]}              # from ALTER TABLE … ADD COLUMN
    assert es["owners"]["via"] == "flyway" and es["owners"]["source"].startswith("api:src/main/resources/db/migration/V1__init.sql#L")


def test_entity_classes_add_what_migrations_do_not_declare(repos):
    vet = entities(repos, "api")["vets"]
    assert vet["via"] == "jpa" and field(vet, "id")["pk"] and field(vet, "first_name")["type"] == "String"
    assert field(vet, "clinic_id")["ref"] == "Clinic"


def test_firestore_collections_from_rules_and_code(repos):
    es = entities(repos, "web")
    assert set(es) == {"users", "users/{userId}/orders", "sessions"}
    assert {f["name"] for f in es["users/{userId}/orders"]["fields"]} == {"total", "status", "createdAt"}
    assert {f["name"] for f in es["sessions"]["fields"]} == {"djName", "startedAt"}
    stores = repos.scan()["web"]["stores"]
    assert stores[0]["kind"] == "document" and stores[0]["engines"] == ["Firestore"]
    assert es["users/{userId}/orders"]["parent"] == "users"


@pytest.mark.parametrize("rel, text, name, check", [
    ("prisma/schema.prisma",
     "model User {\n  id    Int     @id @default(autoincrement())\n  email String  @unique\n  posts Post[]\n}\n"
     "model Post {\n  id       Int  @id\n  authorId Int\n  author   User @relation(fields: [authorId], references: [id])\n}\n",
     "Post", lambda e: field(e, "authorId")["ref"] == "User.id" and field(e, "id")["pk"]),
    ("src/models/user.js",
     "const mongoose = require('mongoose');\nconst userSchema = new mongoose.Schema({\n  name: { type: String, required: true },\n"
     "  org: { type: mongoose.Schema.Types.ObjectId, ref: 'Org' },\n  tags: [String],\n});\n"
     "module.exports = mongoose.model('User', userSchema);\n",
     "User", lambda e: e["kind"] == "collection" and field(e, "org")["ref"] == "Org" and field(e, "name")["type"] == "String"),
    ("src/main/java/demo/Event.java",
     "@Document(collection = \"events\")\npublic class Event {\n  @Id\n  private String id;\n  private Instant at;\n}\n",
     "events", lambda e: e["kind"] == "collection" and field(e, "id")["pk"] and field(e, "at")["type"] == "Instant"),
    ("app/models.py",
     "from django.db import models\n\nclass Pet(models.Model):\n    name = models.CharField(max_length=30)\n"
     "    owner = models.ForeignKey('Owner', on_delete=models.CASCADE)\n",
     "Pet", lambda e: field(e, "owner")["ref"] == "Owner" and field(e, "name")["type"] == "CharField"),
    ("app/db.py",
     "class Order(Base):\n    __tablename__ = 'orders'\n    id = Column(Integer, primary_key=True)\n"
     "    customer_id = Column(Integer, ForeignKey('customers.id'))\n    total: Mapped[float] = mapped_column()\n",
     "orders", lambda e: field(e, "id")["pk"] and field(e, "customer_id")["ref"] == "customers.id"
     and field(e, "total")["type"] == "float"),
    ("src/entity/invoice.entity.ts",
     "@Entity('invoices')\nexport class Invoice {\n  @PrimaryGeneratedColumn()\n  id: number;\n\n  @Column()\n  amount: number;\n\n"
     "  @ManyToOne(() => Customer)\n  customer: Customer;\n}\n",
     "invoices", lambda e: field(e, "id")["pk"] and field(e, "customer")["ref"] == "Customer"),
    ("src/main/resources/db/changelog/db.changelog-master.xml",
     '<databaseChangeLog xmlns="http://www.liquibase.org/xml/ns/dbchangelog"><changeSet id="1" author="a">'
     '<createTable tableName="accounts"><column name="id" type="BIGINT"><constraints primaryKey="true"/></column>'
     '<column name="owner_id" type="BIGINT"><constraints references="owners(id)" foreignKeyName="fk"/></column>'
     '</createTable></changeSet></databaseChangeLog>',
     "accounts", lambda e: e["via"] == "liquibase" and field(e, "id")["pk"] and field(e, "owner_id")["ref"] == "owners.id"),
    ("src/main/resources/db/changelog/db.changelog-master.yaml",
     "databaseChangeLog:\n  - changeSet:\n      id: 1\n      changes:\n        - createTable:\n            tableName: ledgers\n"
     "            columns:\n              - column:\n                  name: id\n                  type: BIGINT\n"
     "                  constraints:\n                    primaryKey: true\n",
     "ledgers", lambda e: e["via"] == "liquibase" and field(e, "id")["pk"]),
    ("lib/data/repo.dart",
     "final ref = FirebaseFirestore.instance.collection('tracks');\n"
     "await ref.add({'title': t, 'artist': a, 'votes': 0});\n",
     "tracks", lambda e: {f["name"] for f in e["fields"]} == {"title", "artist", "votes"}),
])
def test_each_kind_of_source(kit, rel, text, name, check):
    f = kit.ws / "worker" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    from lib import schemas
    es = entities(schemas, "worker")
    assert name in es, list(es)
    assert check(es[name])


def test_each_repo_gets_a_data_page_with_a_generated_er_block(kit, repos):
    written = repos.write_pages(log=lambda _: None)
    assert written == ["docs/data/api.md", "docs/data/web.md"]
    page = (kit.root / "docs" / "data" / "api.md").read_text(encoding="utf-8")
    fm, body = kit.docs.split_fm(page)
    assert fm["type"] == "data-model" and fm["x-generated"] is True and fm["x-owner"] == "ai"
    assert "api:src/main/resources/db/migration/V1__init.sql" in fm["x-sources"]
    assert "<!-- generated:schema repo=api" in body and "erDiagram" in body
    assert 'OWNERS ||--o{ PETS : "owner_id"' in body and "## Ownership" in body and "## Migrations" in body
    assert "Flyway" in body


def test_the_block_follows_the_code_and_a_hand_edit_is_kept(kit, repos):
    repos.write_pages(log=lambda _: None)
    from lib import genblocks
    (kit.ws / "api" / "src" / "main" / "resources" / "db" / "migration" / "V3__x.sql").write_text(
        "CREATE TABLE specialties (id INT PRIMARY KEY);\n", encoding="utf-8")
    assert "docs/data/api.md" in genblocks.refresh()["updated"]
    page = kit.root / "docs" / "data" / "api.md"
    assert "SPECIALTIES" in page.read_text(encoding="utf-8")
    page.write_text(page.read_text(encoding="utf-8").replace("SPECIALTIES {", "SPECIALTIES_MINE {"), encoding="utf-8")
    assert "docs/data/api.md (schema, api)" in genblocks.refresh()["edited"]


def test_an_existing_page_is_never_overwritten(kit, repos):
    page = kit.root / "docs" / "data" / "api.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\ntitle: Our data\n---\n# Our data\n\nWritten by the team.\n", encoding="utf-8")
    kit.docs.confirm([str(page)], by="ana")
    before = page.read_text(encoding="utf-8")
    assert repos.write_pages(log=lambda _: None) == ["docs/data/web.md"]
    assert page.read_text(encoding="utf-8") == before


def test_the_cli(kit, repos):
    import json, os, subprocess, sys
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    run = lambda *a: subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "schemas", *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8", cwd=kit.ws)
    data = json.loads(run("--json").stdout)
    assert {e["name"] for s in data["api"]["stores"] for e in s["entities"]} >= {"owners", "pets", "visits", "vets"}
    r = run()
    assert r.returncode == 0 and "→ docs/data/api.md" in r.stdout and (kit.root / "docs" / "data" / "api.md").is_file()


def test_the_portal_serves_each_repos_model_and_writes_the_pages(kit, repos):
    from lib import serve
    d = serve.api_schemas()
    api = next(r for r in d["repos"] if r["repo"] == "api")
    assert api["entities"] >= 4 and "erDiagram" in api["markdown"] and api["page"] is None
    assert next(r for r in d["repos"] if r["repo"] == "worker")["entities"] == 0
    r = serve.schemas_write()
    assert r["written"] == ["docs/data/api.md", "docs/data/web.md"]
    assert next(x for x in serve.api_schemas()["repos"] if x["repo"] == "api")["page"] == "data/api.md"
