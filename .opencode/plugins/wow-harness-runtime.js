import { spawn } from "node:child_process"
import { appendFile, mkdir, readFile, rm, writeFile } from "node:fs/promises"
import path from "node:path"

const STATE_ROOT = ".wow-harness/state"
const LEGACY_ROOT = ".towow"
const STATE_DIRS = [
  "metrics",
  "guard",
  "progress",
  "logs",
  "active-review-agents",
  "proposals",
]

const RISK_ORDER = { R0: 0, R1: 1, R2: 2, R3: 3, R4: 4 }
const EDIT_TOOLS = new Set(["edit", "write", "apply_patch", "multiedit"])

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
  [".cursor/", "R3"],
  [".opencode/", "R3"],
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

function canonicalPath(worktree, ...parts) {
  return path.join(worktree, STATE_ROOT, ...parts)
}

function legacyPath(worktree, ...parts) {
  return path.join(worktree, LEGACY_ROOT, ...parts)
}

async function ensureRuntimeRoots(worktree) {
  for (const dir of STATE_DIRS) {
    await mkdir(canonicalPath(worktree, dir), { recursive: true })
    await mkdir(legacyPath(worktree, dir), { recursive: true })
  }
  await mkdir(path.dirname(canonicalPath(worktree, "risk-snapshot.json")), { recursive: true })
  await mkdir(path.dirname(legacyPath(worktree, "state", "risk-snapshot.json")), { recursive: true })
}

async function readJsonFallback(paths, fallback) {
  for (const target of paths) {
    try {
      const raw = await readFile(target, "utf8")
      return JSON.parse(raw)
    } catch {}
  }
  return fallback
}

async function writeJsonCompat(worktree, canonicalRelParts, legacyRelParts, payload) {
  const text = `${JSON.stringify(payload, null, 2)}\n`
  const targets = [
    canonicalPath(worktree, ...canonicalRelParts),
    legacyPath(worktree, ...legacyRelParts),
  ]
  for (const target of targets) {
    await mkdir(path.dirname(target), { recursive: true })
    await writeFile(target, text, "utf8")
  }
}

async function appendJsonlCompat(worktree, canonicalRelParts, legacyRelParts, payload) {
  const line = `${JSON.stringify(payload)}\n`
  const targets = [
    canonicalPath(worktree, ...canonicalRelParts),
    legacyPath(worktree, ...legacyRelParts),
  ]
  for (const target of targets) {
    await mkdir(path.dirname(target), { recursive: true })
    let existing = ""
    try {
      existing = await readFile(target, "utf8")
    } catch {}
    await writeFile(target, `${existing}${line}`, "utf8")
  }
}

async function appendVisible(worktree, hook, extra = {}) {
  const quiet = ["1", "true", "yes", "on"].includes((process.env.WOW_HARNESS_QUIET ?? "").toLowerCase())
  if (quiet) return
  try {
    await appendFile(
      canonicalPath(worktree, "harness-visible.jsonl"),
      `${JSON.stringify({ ts: nowIso(), runtime: "opencode", hook, ...extra })}\n`,
      "utf8",
    )
  } catch {}
}

async function removeCompat(worktree, canonicalRelParts, legacyRelParts) {
  const targets = [
    canonicalPath(worktree, ...canonicalRelParts),
    legacyPath(worktree, ...legacyRelParts),
  ]
  for (const target of targets) {
    await rm(target, { force: true })
  }
}

function toRelativeFilePath(filePath, worktree) {
  if (!filePath || typeof filePath !== "string") return ""
  const normalized = path.normalize(filePath)
  const normalizedRoot = path.normalize(worktree)
  if (path.isAbsolute(normalized)) {
    const rel = path.relative(normalizedRoot, normalized)
    return rel.startsWith("..") ? normalized : rel
  }
  return normalized
}

function sessionIdFrom(input) {
  return input?.sessionID ?? input?.sessionId ?? input?.session?.id ?? null
}

function extractPatchPaths(patchText) {
  if (!patchText || typeof patchText !== "string") return []
  const paths = []
  const re = /^\*\*\* (?:Add|Update|Delete) File: (.+)$/gm
  let match
  while ((match = re.exec(patchText)) !== null) {
    paths.push(match[1].trim())
  }
  const moveRe = /^\*\*\* Move to: (.+)$/gm
  while ((match = moveRe.exec(patchText)) !== null) {
    paths.push(match[1].trim())
  }
  return [...new Set(paths)]
}

function changedFilePaths(input, output) {
  if (input.tool === "apply_patch") {
    return extractPatchPaths(output?.args?.patchText ?? input?.args?.patchText ?? "")
  }
  const direct =
    input?.args?.filePath ??
    input?.args?.path ??
    input?.args?.target ??
    output?.args?.filePath ??
    output?.args?.path ??
    ""
  if (direct) return [direct]
  const files = input?.args?.files ?? output?.args?.files ?? []
  if (Array.isArray(files)) return files.filter((item) => typeof item === "string")
  return []
}

function classifyFile(filePath) {
  for (const [prefix, risk] of RISK_ELEVATORS) {
    if (filePath.startsWith(prefix)) return risk
  }
  return "R0"
}

function nowIso() {
  return new Date().toISOString()
}

async function updateRiskSnapshot(worktree, filePath) {
  const relPath = toRelativeFilePath(filePath, worktree)
  if (!relPath) return

  const snapshot = await readJsonFallback(
    [
      canonicalPath(worktree, "risk-snapshot.json"),
      legacyPath(worktree, "state", "risk-snapshot.json"),
    ],
    {
      risk_level: "R0",
      risk_sources: [],
      ratchet_locked: false,
      files_touched: [],
    },
  )

  const filesTouched = Array.isArray(snapshot.files_touched)
    ? [...snapshot.files_touched]
    : []
  if (!filesTouched.includes(relPath)) filesTouched.push(relPath)

  let fileRisk = classifyFile(relPath)
  if (filesTouched.length >= 4 && RISK_ORDER[snapshot.risk_level ?? "R0"] < RISK_ORDER.R1) {
    fileRisk = "R1"
  }

  const currentLevel = snapshot.risk_level ?? "R0"
  if (RISK_ORDER[fileRisk] > RISK_ORDER[currentLevel]) {
    snapshot.risk_level = fileRisk
    snapshot.ratchet_locked = true
    snapshot.risk_sources = Array.isArray(snapshot.risk_sources)
      ? snapshot.risk_sources
      : []
    snapshot.risk_sources.push({
      type: "path",
      value: relPath,
      elevated_to: fileRisk,
      ts: nowIso(),
      source: "opencode",
    })
  }

  snapshot.files_touched = filesTouched
  snapshot.last_updated = nowIso()
  await writeJsonCompat(
    worktree,
    ["risk-snapshot.json"],
    ["state", "risk-snapshot.json"],
    snapshot,
  )
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

async function runGuardFeedback(worktree, filePath) {
  const relPath = toRelativeFilePath(filePath, worktree)
  if (!relPath) return null
  const payload = JSON.stringify({
    tool_name: "Edit",
    tool_input: { file_path: path.join(worktree, relPath) },
  })
  const result = await runProcess(
    "python3",
    [path.join(worktree, "scripts", "guard-feedback.py")],
    { cwd: worktree, stdin: payload, timeoutMs: 45000 },
  )
  const text = [result.stderr, result.stdout].filter(Boolean).join("\n").trim()
  if (!text) return null
  return {
    file_path: relPath,
    text,
    exit_code: result.code,
    timed_out: result.timedOut,
  }
}

async function recordGuardFeedback(worktree, feedback) {
  if (!feedback) return
  await appendJsonlCompat(
    worktree,
    ["logs", "opencode-feedback.jsonl"],
    ["logs", "opencode-feedback.jsonl"],
    {
      ts: nowIso(),
      event: "guard_feedback",
      source: "opencode",
      file_path: feedback.file_path,
      exit_code: feedback.exit_code,
      timed_out: feedback.timed_out,
      bytes: feedback.text.length,
    },
  )
  const latest = `# wow-harness OpenCode Feedback\n\nFile: ${feedback.file_path}\n\n${feedback.text}\n`
  await writeFile(canonicalPath(worktree, "logs", "opencode-latest-feedback.md"), latest, "utf8")
}

async function promptSession(client, sessionId, text) {
  if (!client?.session?.prompt || !sessionId || !text) return false
  try {
    await client.session.prompt({
      path: { id: sessionId },
      body: {
        parts: [{
          type: "text",
          text,
        }],
      },
    })
    return true
  } catch {
    return false
  }
}

export const WowHarnessRuntimePlugin = async ({ worktree, client }) => {
  await ensureRuntimeRoots(worktree)
  await appendVisible(worktree, "plugin.init")

  return {
    event: async ({ event }) => {
      if (!event?.type) return

      if (event.type === "session.created") {
        await ensureRuntimeRoots(worktree)
        await appendVisible(worktree, "session.created", {
          session_id: event.sessionID ?? event.sessionId ?? null,
        })
        await removeCompat(
          worktree,
          ["risk-snapshot.json"],
          ["state", "risk-snapshot.json"],
        )
      }

      if (event.type === "session.created" || event.type === "session.idle" || event.type === "session.compacted") {
        await appendJsonlCompat(
          worktree,
          ["metrics", "opencode-session-events.jsonl"],
          ["metrics", "opencode-session-events.jsonl"],
          {
            ts: nowIso(),
            event: event.type,
            source: "opencode",
            session_id: event.sessionID ?? event.sessionId ?? null,
          },
        )
      }
    },

    "tool.execute.before": async (input, output) => {
      if (input.tool === "read") {
        const filePath = output?.args?.filePath ?? input?.args?.filePath ?? ""
        if (typeof filePath === "string" && filePath.includes(".env")) {
          throw new Error("wow-harness: reading .env files is blocked")
        }
      }
    },

    "tool.execute.after": async (input, output) => {
      if (!EDIT_TOOLS.has(input.tool)) return

      const filePaths = changedFilePaths(input, output)
      if (!filePaths.length) return
      await appendVisible(worktree, "tool.execute.after", { tool: input.tool })

      const feedbackTexts = []
      for (const filePath of filePaths) {
        await updateRiskSnapshot(worktree, filePath)
        const feedback = await runGuardFeedback(worktree, filePath)
        if (feedback) {
          await recordGuardFeedback(worktree, feedback)
          feedbackTexts.push(feedback.text)
        }
      }

      await appendJsonlCompat(
        worktree,
        ["metrics", "guard-events.jsonl"],
        ["metrics", "guard-events.jsonl"],
        {
          ts: nowIso(),
          event: "opencode_edit",
          source: "opencode",
          tool: input.tool,
          file_paths: filePaths.map((filePath) => toRelativeFilePath(filePath, worktree)),
        },
      )

      if (feedbackTexts.length) {
        const injected = await promptSession(
          client,
          sessionIdFrom(input),
          `wow-harness feedback after ${input.tool}:\n\n${feedbackTexts.join("\n\n---\n\n")}`.slice(0, 12000),
        )
        await appendVisible(worktree, injected ? "guard-feedback.prompted" : "guard-feedback.logged", {
          tool: input.tool,
          feedback_count: feedbackTexts.length,
        })
      }
    },

    "experimental.session.compacting": async (_input, output) => {
      output.context.push(`
## wow-harness continuation checklist

- Persist current objective and changed files before ending the session.
- Keep `.wow-harness/state/risk-snapshot.json` aligned with edited files.
- Do not claim completion without concrete verification evidence.
- If code changed materially, route final review through a read-only reviewer agent.
`.trim())
    },

    stop: async (input) => {
      const sessionId = input?.sessionID ?? input?.sessionId ?? null
      const snapshot = await readJsonFallback(
        [
          canonicalPath(worktree, "risk-snapshot.json"),
          legacyPath(worktree, "state", "risk-snapshot.json"),
        ],
        { risk_level: "R0", files_touched: [] },
      )

      const progress = await readJsonFallback(
        [canonicalPath(worktree, "progress", "current.json")],
        { done: false, remaining: [] },
      )

      const proposal = {
        ts: nowIso(),
        session_id: sessionId,
        source: "opencode",
        risk_level: snapshot.risk_level ?? "R0",
        files_touched: snapshot.files_touched ?? [],
        progress_done: progress.done ?? false,
        can_complete: false,
        blocking_reasons: [],
      }

      if (snapshot.risk_level && ["R3", "R4"].includes(snapshot.risk_level)) {
        proposal.blocking_reasons.push(`high risk level: ${snapshot.risk_level}`)
      }

      if (!proposal.progress_done && (!progress.remaining || progress.remaining.length > 0)) {
        proposal.blocking_reasons.push("progress not marked as done")
      }

      proposal.can_complete = proposal.blocking_reasons.length === 0

      await writeJsonCompat(
        worktree,
        ["completion-proposal.json"],
        ["state", "completion-proposal.json"],
        proposal,
      )

      if (!proposal.can_complete) {
        const reasons = proposal.blocking_reasons.join("; ")
        await client.session.prompt({
          path: { id: sessionId },
          body: {
            parts: [{
              type: "text",
              text: `wow-harness: cannot complete yet. Reasons: ${reasons}. Please address these before stopping.`,
            }],
          },
        })
      }
    },
  }
}
