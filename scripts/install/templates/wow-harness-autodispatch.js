import { spawn } from "node:child_process"
import { appendFile, mkdir, readFile, stat, writeFile } from "node:fs/promises"
import path from "node:path"

function nowIso() {
  return new Date().toISOString()
}

const RISK_ORDER = { R0: 0, R1: 1, R2: 2, R3: 3, R4: 4 }
const RISK_ELEVATORS = [
  ["scripts/deploy", "R4"],
  ["backend/product/db/migration", "R4"],
  ["CLAUDE.md", "R3"],
  ["AGENTS.md", "R3"],
  [".wow-harness/", "R3"],
  [".claude/settings.json", "R3"],
  [".claude/skills/", "R3"],
  [".claude/rules/", "R3"],
  [".claude/agents/", "R3"],
  [".codex/", "R3"],
  [".cursor/", "R3"],
  [".opencode/", "R3"],
  ["scripts/codex/", "R3"],
  ["scripts/hooks/", "R3"],
  ["scripts/checks/", "R3"],
  ["scripts/install/", "R3"],
  [".github/", "R3"],
  ["backend/product/routes/", "R2"],
  ["backend/product/config.py", "R2"],
  ["backend/server.py", "R2"],
  ["docs/decisions/ADR-", "R2"],
  ["mcp-server/", "R2"],
  ["mcp-server-node/", "R2"],
  ["website/app/", "R2"],
]

function classifyFile(relPath) {
  for (const [prefix, risk] of RISK_ELEVATORS) {
    if (relPath.startsWith(prefix)) return risk
  }
  return "R0"
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

async function appendVisible(worktree, hook, extra = {}) {
  const quiet = ["1", "true", "yes", "on"].includes((process.env.WOW_HARNESS_QUIET ?? "").toLowerCase())
  if (quiet) return
  try {
    const target = path.join(worktree, ".wow-harness", "state", "harness-visible.jsonl")
    await mkdir(path.dirname(target), { recursive: true })
    await appendFile(target, `${JSON.stringify({ ts: nowIso(), runtime: "opencode", hook, ...extra })}\n`, "utf8")
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

function runProcess(command, args, { cwd, stdin = "", timeoutMs = 45000 } = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, { cwd, stdio: ["pipe", "pipe", "pipe"] })
    let stdout = ""
    let stderr = ""
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      child.kill("SIGKILL")
    }, timeoutMs)
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString()
    })
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString()
    })
    child.on("error", (error) => {
      clearTimeout(timer)
      resolve({ code: 127, stdout, stderr: `${stderr}${error.message}`, timedOut })
    })
    child.on("close", (code) => {
      clearTimeout(timer)
      resolve({ code: code ?? 0, stdout, stderr, timedOut })
    })
    child.stdin.end(stdin)
  })
}

function toRelative(worktree, filePath) {
  if (!filePath || typeof filePath !== "string") return ""
  return path.isAbsolute(filePath) ? path.relative(worktree, filePath) : filePath
}

function extractPatchPaths(patchText) {
  if (!patchText || typeof patchText !== "string") return []
  const paths = []
  const re = /^\*\*\* (?:Add|Update|Delete) File: (.+)$/gm
  let match
  while ((match = re.exec(patchText)) !== null) paths.push(match[1].trim())
  const moveRe = /^\*\*\* Move to: (.+)$/gm
  while ((match = moveRe.exec(patchText)) !== null) paths.push(match[1].trim())
  return [...new Set(paths)]
}

function changedFilePaths(input, output) {
  if (input.tool === "apply_patch") {
    return extractPatchPaths(output?.args?.patchText ?? input?.args?.patchText ?? "")
  }
  const direct = input?.args?.filePath ?? input?.args?.path ?? output?.args?.filePath ?? output?.args?.path ?? ""
  return direct ? [direct] : []
}

function sessionIdFrom(input) {
  return input?.sessionID ?? input?.sessionId ?? input?.session?.id ?? null
}

async function promptSession(client, sessionId, text) {
  if (!client?.session?.prompt || !sessionId || !text) return false
  try {
    await client.session.prompt({
      path: { id: sessionId },
      body: { parts: [{ type: "text", text }] },
    })
    return true
  } catch {
    return false
  }
}

async function runGuardFeedback(worktree, filePath) {
  const rel = toRelative(worktree, filePath)
  if (!rel) return null
  const payload = JSON.stringify({ tool_name: "Edit", tool_input: { file_path: path.join(worktree, rel) } })
  const result = await runProcess(
    "python3",
    [path.join(worktree, "scripts", "guard-feedback.py")],
    { cwd: worktree, stdin: payload, timeoutMs: 45000 },
  )
  const text = [result.stderr, result.stdout].filter(Boolean).join("\n").trim()
  if (!text) return null
  const latest = path.join(worktree, ".wow-harness", "state", "logs", "opencode-latest-feedback.md")
  await mkdir(path.dirname(latest), { recursive: true })
  await writeFile(latest, `# wow-harness OpenCode Feedback\n\nFile: ${rel}\n\n${text}\n`, "utf8")
  await log({ ts: nowIso(), event: "guard.feedback", filePath: rel, exitCode: result.code, timedOut: result.timedOut })
  return text
}

export const WowHarnessAutodispatch = async ({ worktree, client }) => {
  const manifest = path.join(worktree, ".wow-harness", "MANIFEST.yaml")
  const enabled = await exists(manifest)
  await log({ ts: nowIso(), event: "plugin.init", enabled, worktree })
  if (enabled) await appendVisible(worktree, "global-plugin.init")

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

    "tool.execute.after": async (input, output) => {
      if (!["edit", "write", "apply_patch", "multiedit"].includes(input.tool)) return
      const filePaths = changedFilePaths(input, output)
      if (!filePaths.length) return
      await appendVisible(worktree, "global-tool.execute.after", { tool: input.tool })

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

      const feedbackTexts = []
      for (const filePath of filePaths) {
        const rel = toRelative(worktree, filePath)
        if (Array.isArray(snap.files_touched) && !snap.files_touched.includes(rel)) {
          snap.files_touched.push(rel)
        }
        const feedback = await runGuardFeedback(worktree, filePath)
        if (feedback) feedbackTexts.push(feedback)
      }
      snap.last_updated = nowIso()

      let maxRisk = snap.risk_level ?? "R0"
      for (const f of snap.files_touched) {
        const r = classifyFile(f)
        if (RISK_ORDER[r] > RISK_ORDER[maxRisk]) maxRisk = r
      }
      if (snap.files_touched.length >= 4 && RISK_ORDER[maxRisk] < RISK_ORDER.R1) maxRisk = "R1"
      snap.risk_level = maxRisk

      await writeJsonCompat(worktree, ["risk-snapshot.json"], ["state", "risk-snapshot.json"], snap)
      await log({ ts: nowIso(), event: "risk.snapshot.update", filePaths: filePaths.map((p) => toRelative(worktree, p)) })
      if (feedbackTexts.length) {
        const injected = await promptSession(
          client,
          sessionIdFrom(input),
          `wow-harness feedback after ${input.tool}:\n\n${feedbackTexts.join("\n\n---\n\n")}`.slice(0, 12000),
        )
        await appendVisible(worktree, injected ? "global-guard-feedback.prompted" : "global-guard-feedback.logged", {
          tool: input.tool,
          feedback_count: feedbackTexts.length,
        })
      }
    },
  }
}
