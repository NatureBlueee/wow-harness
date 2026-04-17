import { appendFile, mkdir, readFile, stat } from "node:fs/promises"
import path from "node:path"

function nowIso() {
  return new Date().toISOString()
}

async function exists(p) {
  try {
    await stat(p)
    return true
  } catch {
    return false
  }
}

async function log(record) {
  try {
    const dir = path.join(process.env.HOME ?? "", ".wow-agent-hooks", "logs")
    await mkdir(dir, { recursive: true })
    await appendFile(path.join(dir, "opencode-dispatch.jsonl"), `${JSON.stringify(record)}\n`, "utf8")
  } catch {}
}

function isEnvFile(filePath) {
  const base = path.basename(filePath)
  return base === ".env" || base.startsWith(".env.")
}

async function loadJson(filePath, fallback) {
  try {
    const raw = await readFile(filePath, "utf8")
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}

async function writeJsonCompat(worktree, canonicalRel, legacyRel, payload) {
  const text = `${JSON.stringify(payload, null, 2)}\n`
  const fs = await import("node:fs/promises")
  const targets = [
    path.join(worktree, ".wow-harness", "state", ...canonicalRel),
    path.join(worktree, ".towow", ...legacyRel),
  ]
  for (const t of targets) {
    await fs.mkdir(path.dirname(t), { recursive: true })
    await fs.writeFile(t, text, "utf8")
  }
}

export const WowHarnessAutodispatch = async ({ worktree }) => {
  const manifest = path.join(worktree, ".wow-harness", "MANIFEST.yaml")
  const enabled = await exists(manifest)
  await log({ ts: nowIso(), event: "plugin.init", enabled, worktree })

  if (!enabled) {
    return {}
  }

  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "read") return
      const filePath = output?.args?.filePath ?? input?.args?.filePath ?? ""
      if (typeof filePath === "string" && isEnvFile(filePath)) {
        await log({ ts: nowIso(), event: "block.env.read", filePath })
        throw new Error("wow-harness: reading .env files is blocked")
      }
    },

    "tool.execute.after": async (input) => {
      if (!["edit", "write"].includes(input.tool)) return
      const filePath = input?.args?.filePath ?? input?.args?.path ?? ""
      if (!filePath) return

      const canonical = path.join(worktree, ".wow-harness", "state", "risk-snapshot.json")
      const legacy = path.join(worktree, ".towow", "state", "risk-snapshot.json")
      const snap = await loadJson(
        canonical,
        await loadJson(legacy, {
          risk_level: "R0",
          risk_sources: [],
          ratchet_locked: false,
          files_touched: [],
        }),
      )

      const rel = path.isAbsolute(filePath) ? path.relative(worktree, filePath) : filePath
      if (Array.isArray(snap.files_touched) && !snap.files_touched.includes(rel)) {
        snap.files_touched.push(rel)
      }
      snap.last_updated = nowIso()

      await writeJsonCompat(worktree, ["risk-snapshot.json"], ["state", "risk-snapshot.json"], snap)
      await log({ ts: nowIso(), event: "risk.snapshot.update", filePath: rel })
    },
  }
}
