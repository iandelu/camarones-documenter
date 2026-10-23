"""Firebase projects in the first-look C4 draft (S12): one Firestore and one Storage per Firebase project, shared by
every repo that uses them (not a database per repo), a Cloud Functions container for a repo's functions/ folder, the
calls from the apps to it, and Firebase Auth as an external system — a correct first C4 for projects like a Flutter
admin app plus a web app on Firebase."""
from __future__ import annotations

import json

import pytest

PUBSPEC = """name: admin_dj
dependencies:
  flutter:
    sdk: flutter
  firebase_core: ^2.24.0
  cloud_firestore: ^4.13.0
  firebase_storage: ^11.5.0
  firebase_auth: ^4.15.0
  cloud_functions: ^4.5.0
"""
DART = """final db = FirebaseFirestore.instance;
final fn = FirebaseFunctions.instance.httpsCallable('startSession');
"""
WEB_PKG = {"name": "user-web", "dependencies": {"react": "18.2.0", "firebase": "10.7.0"}}
WEB_SRC = """import { getFirestore } from 'firebase/firestore';
import { getFunctions, httpsCallable } from 'firebase/functions';
import { getStorage } from 'firebase/storage';
export const vote = httpsCallable(getFunctions(), 'vote');
"""
FN_PKG = {"name": "functions", "dependencies": {"firebase-admin": "12.0.0", "firebase-functions": "4.6.0"}}
FN_SRC = """const admin = require('firebase-admin');
const functions = require('firebase-functions');
exports.vote = functions.https.onCall(async (data) => admin.firestore().collection('votes').add(data));
"""


@pytest.fixture
def firebase(kit):
    ws = kit.docs.workspace()
    for r in ws["repos"]:
        r["kind"] = {"worker": "mobileApp", "web": "webapp"}.get(r["name"], r["kind"])
    kit.docs.save_workspace(ws)
    admin, web = kit.ws / "worker", kit.ws / "web"
    (admin / "pubspec.yaml").write_text(PUBSPEC, encoding="utf-8")
    (admin / "lib").mkdir()
    (admin / "lib" / "main.dart").write_text(DART, encoding="utf-8")
    (admin / "pyproject.toml").unlink()
    (web / "package.json").write_text(json.dumps(WEB_PKG), encoding="utf-8")
    (web / "src" / "firebase.js").write_text(WEB_SRC, encoding="utf-8")
    (web / ".firebaserc").write_text('{"projects": {"default": "enjoy-the-club"}}', encoding="utf-8")
    (web / "firebase.json").write_text('{"functions": {"source": "functions"}, "hosting": {"public": "build"}}', encoding="utf-8")
    (web / "functions").mkdir()
    (web / "functions" / "package.json").write_text(json.dumps(FN_PKG), encoding="utf-8")
    (web / "functions" / "index.js").write_text(FN_SRC, encoding="utf-8")
    from lib import quickarch
    return quickarch


def test_one_firestore_and_one_storage_for_the_project_shared_by_every_repo(firebase):
    m = firebase.scan()
    fs = m["dbs"]["Firestore:enjoy-the-club"]
    assert fs["label"] == "Firestore" and fs["users"] == {"worker", "web", "web Cloud Functions"}
    assert m["dbs"]["Firebase Storage:enjoy-the-club"]["users"] == {"worker", "web"}
    assert not [k for k in m["dbs"] if k.startswith("Firestore:") and k != "Firestore:enjoy-the-club"]


def test_cloud_functions_are_a_container_the_apps_call(firebase):
    m = firebase.scan()
    fn = m["repos"]["web Cloud Functions"]
    assert fn["kind"] == "service" and "Cloud Functions" in fn["tech"] and fn["repo"] == "web"
    edges = {(a, b, label) for a, b, _, label in m["edges"]}
    assert ("web", "web Cloud Functions", "calls") in edges and ("worker", "web Cloud Functions", "calls") in edges
    assert ("web Cloud Functions", "Firestore:enjoy-the-club", "reads/writes") in edges
    assert "Firebase Auth" in m["idps"]


def test_the_c4_draft_is_valid_and_readable(firebase, kit, monkeypatch):
    monkeypatch.setattr(firebase, "which", lambda name: None)
    c4 = firebase.render_c4(firebase.scan(), "enjoy")["model.c4"]
    assert "webCloudFunctions = service 'web Cloud Functions'" in c4
    assert "database 'Firestore: enjoy-the-club'" in c4 and "#shared-db" in c4
    assert "database 'Firebase Storage: enjoy-the-club'" in c4
    assert "worker = mobileApp 'worker'" in c4
    assert "-[sync]-> enjoy.webCloudFunctions 'calls'" in c4
    block = c4.split("webCloudFunctions = service")[1].split("\n    }")[0]
    assert "metadata { repo 'web' }" in block and "Cloud Functions · Node.js" in block


@pytest.mark.skipif(not __import__("shutil").which("likec4"), reason="likec4 not installed")
def test_likec4_accepts_the_firebase_draft(firebase, tmp_path):
    import subprocess
    for name, text in firebase.render_c4(firebase.scan(), "enjoy").items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    r = subprocess.run(["likec4", "validate", "."], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
