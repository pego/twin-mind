"""Optional Oxc-powered JavaScript/TypeScript entity extraction bridge."""

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional

from twin_mind.entity_extractors import EntityExtractionResult


def _module_name_from_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/").strip("/")
    path = Path(normalized)
    stemmed = path.with_suffix("")
    parts = list(stemmed.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return "module"
    return ".".join(parts)


@lru_cache(maxsize=1)
def _find_node_binary() -> Optional[str]:
    return shutil.which("node")


def _run_oxc_driver(payload: dict, cwd: Optional[Path]) -> Optional[dict]:
    node_binary = _find_node_binary()
    if not node_binary:
        return None

    try:
        completed = subprocess.run(
            [node_binary, "--input-type=module", "-e", _OXC_DRIVER],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=8,
            check=False,
            cwd=str(cwd) if cwd else None,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0:
        return None
    raw = (completed.stdout or "").strip()
    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


_OXC_DRIVER = r"""
import fs from "node:fs";

const stdin = fs.readFileSync(0, "utf8");
const payload = JSON.parse(stdin);
const { filePath, moduleName, code } = payload;

let parseSync = null;
try {
  const parserMod = await import("oxc-parser");
  parseSync = parserMod.parseSync || parserMod.default?.parseSync || parserMod.default;
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, reason: "parser-unavailable" }));
  process.exit(0);
}

if (typeof parseSync !== "function") {
  process.stdout.write(JSON.stringify({ ok: false, reason: "invalid-parser-api" }));
  process.exit(0);
}

function lineFromOffset(source, offset) {
  if (typeof offset !== "number" || offset < 0) return 1;
  let line = 1;
  const limit = Math.min(offset, source.length);
  for (let i = 0; i < limit; i++) {
    if (source.charCodeAt(i) === 10) line++;
  }
  return line;
}

function lineOf(node) {
  if (!node || typeof node !== "object") return 1;
  if (node.loc?.start?.line) return Number(node.loc.start.line) || 1;
  if (typeof node.start === "number") return lineFromOffset(code, node.start);
  return 1;
}

function moduleNameFromImportPath(currentModule, importPath) {
  const raw = String(importPath || "").trim().replaceAll("\\", "/");
  if (!raw) return "";
  const noExt = raw.replace(/\.(js|jsx|mjs|cjs|ts|tsx)$/i, "");
  if (noExt.startsWith(".")) {
    const base = currentModule.split(".").slice(0, -1).filter(Boolean);
    for (const part of noExt.split("/")) {
      if (!part || part === ".") continue;
      if (part === "..") {
        if (base.length) base.pop();
      } else {
        base.push(part);
      }
    }
    return base.join(".");
  }
  return noExt.replaceAll("/", ".");
}

function keyName(node) {
  if (!node || typeof node !== "object") return "";
  if (node.type === "Identifier") return node.name || "";
  if (node.type === "Literal") return String(node.value ?? "");
  if (typeof node.name === "string") return node.name;
  return "";
}

function calleeName(node) {
  if (!node || typeof node !== "object") return "";
  if (node.type === "Identifier") return node.name || "";
  if (node.type === "ThisExpression") return "this";
  if (node.type === "Super") return "super";
  if (node.type === "MemberExpression" || node.type === "OptionalMemberExpression") {
    if (node.computed) return "";
    const objectName = calleeName(node.object);
    const propertyName = keyName(node.property);
    if (!propertyName) return objectName;
    return objectName ? `${objectName}.${propertyName}` : propertyName;
  }
  return "";
}

function walk(node, visit) {
  if (!node || typeof node !== "object") return;
  visit(node);
  for (const value of Object.values(node)) {
    if (!value) continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item && typeof item === "object") walk(item, visit);
      }
      continue;
    }
    if (typeof value === "object") walk(value, visit);
  }
}

function collectCalls(node, scope, addRelation) {
  walk(node, (cur) => {
    if (cur.type === "CallExpression" || cur.type === "OptionalCallExpression") {
      const name = calleeName(cur.callee);
      if (name) addRelation(scope, name, "calls", lineOf(cur));
      return;
    }
    if (cur.type === "NewExpression") {
      const name = calleeName(cur.callee);
      if (name) addRelation(scope, name, "calls", lineOf(cur));
    }
  });
}

let parseResult;
try {
  parseResult = parseSync(filePath, code);
} catch (_firstError) {
  try {
    parseResult = parseSync(code);
  } catch (_secondError) {
    process.stdout.write(JSON.stringify({ ok: false, reason: "parse-failed" }));
    process.exit(0);
  }
}

const program = parseResult?.program ?? parseResult?.ast ?? parseResult;
if (!program || !Array.isArray(program.body)) {
  process.stdout.write(JSON.stringify({ ok: false, reason: "invalid-ast" }));
  process.exit(0);
}

const entities = [];
const relations = [];
const seen = new Set();

function addRelation(src, dst, relation, line) {
  if (!src || !dst || !relation) return;
  relations.push({
    file_path: filePath,
    src_qualname: src,
    dst_name: dst,
    relation,
    line: Number(line || 0),
  });
}

function addEntity(parent, name, kind, line) {
  const qualname = `${parent}.${name}`;
  const key = `${kind}:${qualname}`;
  if (seen.has(key)) return qualname;
  seen.add(key);
  entities.push({
    file_path: filePath,
    name,
    qualname,
    kind,
    line: Number(line || 0),
  });
  addRelation(parent, qualname, "defines", line);
  return qualname;
}

entities.push({
  file_path: filePath,
  name: moduleName,
  qualname: moduleName,
  kind: "module",
  line: 1,
});
seen.add(`module:${moduleName}`);

function handleStatement(node) {
  if (!node || typeof node !== "object") return;

  if (node.type === "ExportNamedDeclaration" || node.type === "ExportDefaultDeclaration") {
    if (node.declaration) handleStatement(node.declaration);
    return;
  }

  if (node.type === "ImportDeclaration") {
    const sourcePath = node.source?.value ?? node.source?.raw ?? "";
    const moduleSymbol = moduleNameFromImportPath(moduleName, sourcePath);
    const line = lineOf(node);
    if (moduleSymbol) addRelation(moduleName, moduleSymbol, "imports", line);

    for (const spec of node.specifiers || []) {
      if (!spec || typeof spec !== "object") continue;
      const local = spec.local?.name || "";
      if (!local || !moduleSymbol) continue;

      if (spec.type === "ImportDefaultSpecifier") {
        addRelation(moduleName, `${local}=${moduleSymbol}`, "imports_alias", line);
        continue;
      }
      if (spec.type === "ImportNamespaceSpecifier") {
        addRelation(moduleName, `${local}=${moduleSymbol}`, "imports_alias", line);
        continue;
      }
      if (spec.type === "ImportSpecifier") {
        const imported = spec.imported?.name || spec.imported?.value || "";
        if (!imported) continue;
        const target = `${moduleSymbol}.${imported}`;
        addRelation(moduleName, target, "imports", line);
        addRelation(moduleName, `${local}=${target}`, "imports_alias", line);
      }
    }
    return;
  }

  if (node.type === "ClassDeclaration" && node.id?.name) {
    const className = node.id.name;
    const classLine = lineOf(node);
    const classQual = addEntity(moduleName, className, "class", classLine);

    const base = calleeName(node.superClass);
    if (base) addRelation(classQual, base, "inherits", classLine);

    const methods = node.body?.body || [];
    for (const method of methods) {
      const key = keyName(method.key);
      if (!key) continue;
      if (method.kind === "constructor") continue;
      const methodQual = addEntity(classQual, key, "method", lineOf(method));
      const value = method.value || method;
      const body = value.body || method.body;
      if (body) collectCalls(body, methodQual, addRelation);
    }
    return;
  }

  if (node.type === "FunctionDeclaration" && node.id?.name) {
    const fnQual = addEntity(moduleName, node.id.name, "function", lineOf(node));
    if (node.body) collectCalls(node.body, fnQual, addRelation);
    return;
  }

  if (node.type === "VariableDeclaration") {
    for (const decl of node.declarations || []) {
      const localName = decl.id?.name || "";
      if (!localName) continue;
      const init = decl.init;
      if (!init || typeof init !== "object") continue;
      if (init.type === "ArrowFunctionExpression" || init.type === "FunctionExpression") {
        const fnQual = addEntity(moduleName, localName, "function", lineOf(decl));
        if (init.body) collectCalls(init.body, fnQual, addRelation);
      }
    }
  }
}

for (const stmt of program.body) handleStatement(stmt);

process.stdout.write(JSON.stringify({ ok: true, entities, relations }));
"""


def extract_javascript_entities_with_oxc(
    file_path: str,
    content: str,
) -> Optional[EntityExtractionResult]:
    """Try extracting entities/relations with oxc-parser. Returns None on fallback."""
    payload = {
        "filePath": file_path,
        "moduleName": _module_name_from_path(file_path),
        "code": content,
    }

    working_dirs = [Path.cwd()]
    runtime_dir = Path.home() / ".twin-mind"
    if runtime_dir.exists() and runtime_dir not in working_dirs:
        working_dirs.append(runtime_dir)

    parsed: Optional[dict] = None
    for cwd in working_dirs:
        parsed = _run_oxc_driver(payload, cwd=cwd)
        if parsed and parsed.get("ok"):
            break
    if not parsed or not parsed.get("ok"):
        return None

    entities = parsed.get("entities", [])
    relations = parsed.get("relations", [])
    if not isinstance(entities, list) or not isinstance(relations, list):
        return None
    return entities, relations
