/**
 * Clarvis Context Engine — Phase 1 MVP
 *
 * Injects ClarvisDB brain context into every M2.5 conversation turn
 * via the OpenClaw ContextEngine plugin interface.
 *
 * Architecture: TypeScript plugin → Python subprocess (prompt_builder.py)
 * Lifecycle: assemble() injects context, ingest()/compact() delegate to legacy
 */

import { execFile } from "node:child_process";
import type {
  ContextEngine,
  ContextEngineInfo,
  AssembleResult,
  CompactResult,
  IngestResult,
  IngestBatchResult,
  BootstrapResult,
} from "openclaw/plugin-sdk/context-engine";
import type { AgentMessage } from "@mariozechner/pi-agent-core";

const WORKSPACE = "/home/agent/.openclaw/workspace";
const PROMPT_BUILDER = `${WORKSPACE}/scripts/prompt_builder.py`;

type ClarvisConfig = {
  contextTier?: "minimal" | "standard" | "full";
  maxLatencyMs?: number;
  skipShortMessages?: number;
};

/**
 * Call a Python script and return stdout.
 * Times out after maxLatencyMs (default 5s) to avoid blocking the gateway.
 */
function callPython(
  script: string,
  args: string[],
  timeoutMs: number = 5000,
): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(
      "python3",
      [script, ...args],
      {
        cwd: `${WORKSPACE}/scripts`,
        timeout: timeoutMs,
        env: {
          ...process.env,
          PYTHONPATH: `${WORKSPACE}/scripts:${WORKSPACE}`,
        },
      },
      (err, stdout, stderr) => {
        if (err) {
          // On timeout or error, resolve empty — don't block the conversation
          resolve("");
        } else {
          resolve(stdout.trim());
        }
      },
    );
  });
}

/**
 * Extract text content from an AgentMessage.
 */
function extractText(msg: AgentMessage | undefined): string {
  if (!msg) return "";
  if (typeof msg.content === "string") return msg.content;
  if (Array.isArray(msg.content)) {
    return msg.content
      .filter((p: any) => p.type === "text")
      .map((p: any) => p.text || "")
      .join(" ");
  }
  return "";
}

/**
 * Rough token estimate (~4 chars per token).
 */
function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

function estimateMessagesTokens(messages: AgentMessage[]): number {
  return messages.reduce((sum, m) => sum + estimateTokens(extractText(m)), 0);
}

export class ClarvisContextEngine implements ContextEngine {
  readonly info: ContextEngineInfo = {
    id: "clarvis-context",
    name: "Clarvis Context Engine",
    version: "0.1.0",
    ownsCompaction: false, // Delegate compaction to legacy for now
  };

  private config: ClarvisConfig;

  constructor(config?: ClarvisConfig) {
    this.config = {
      contextTier: config?.contextTier || "standard",
      maxLatencyMs: config?.maxLatencyMs || 5000,
      skipShortMessages: config?.skipShortMessages || 20,
    };
  }

  async bootstrap(params: {
    sessionId: string;
    sessionFile: string;
  }): Promise<BootstrapResult> {
    return { bootstrapped: true, reason: "clarvis-context ready" };
  }

  /**
   * Phase 1 MVP: Inject ClarvisDB brain context as systemPromptAddition.
   * Calls prompt_builder.py context-brief for a compact brain brief.
   */
  async assemble(params: {
    sessionId: string;
    messages: AgentMessage[];
    tokenBudget?: number;
  }): Promise<AssembleResult> {
    const { messages } = params;
    const baseTokens = estimateMessagesTokens(messages);

    // Extract latest user message as the query for brain introspection
    const userMessages = messages.filter((m) => m.role === "user");
    const lastUser = userMessages[userMessages.length - 1];
    const query = extractText(lastUser);

    // Skip brain context for very short messages (greetings, acks)
    if (query.length < (this.config.skipShortMessages || 20)) {
      return { messages, estimatedTokens: baseTokens };
    }

    // Call prompt_builder.py for a compact brain brief
    const tier = this.config.contextTier || "standard";
    const brief = await callPython(
      PROMPT_BUILDER,
      ["context-brief", "--task", query, "--tier", tier],
      this.config.maxLatencyMs || 5000,
    );

    if (!brief) {
      // Python bridge failed or timed out — serve messages without brain context
      return { messages, estimatedTokens: baseTokens };
    }

    return {
      messages,
      estimatedTokens: baseTokens + estimateTokens(brief),
      systemPromptAddition: `\n--- BRAIN CONTEXT ---\n${brief}\n---`,
    };
  }

  /**
   * Phase 1: Minimal ingest — acknowledge but don't store yet.
   * Phase 2 will add brain.capture() for user messages.
   */
  async ingest(params: {
    sessionId: string;
    message: AgentMessage;
    isHeartbeat?: boolean;
  }): Promise<IngestResult> {
    // Phase 1: no-op ingest, delegate to legacy
    return { ingested: false };
  }

  /**
   * Phase 1: Delegate compaction to legacy engine.
   */
  async compact(params: {
    sessionId: string;
    sessionFile: string;
    tokenBudget?: number;
    force?: boolean;
    currentTokenCount?: number;
    compactionTarget?: "budget" | "threshold";
    customInstructions?: string;
    legacyParams?: Record<string, unknown>;
  }): Promise<CompactResult> {
    // ownsCompaction=false means OpenClaw will use legacy compaction
    return { ok: true, compacted: false, reason: "delegated-to-legacy" };
  }

  async dispose(): Promise<void> {
    // Nothing to clean up
  }
}

// --- Plugin entry point ---

const plugin = {
  id: "clarvis-context",
  name: "Clarvis Context Engine",
  kind: "context-engine" as const,
  version: "0.1.0",

  activate(api: any) {
    const pluginConfig = (api.pluginConfig || {}) as ClarvisConfig;
    api.registerContextEngine(
      "clarvis-context",
      () => new ClarvisContextEngine(pluginConfig),
    );
    api.logger.info(
      `Clarvis Context Engine registered (tier=${pluginConfig.contextTier || "standard"})`,
    );
  },
};

export default plugin;
