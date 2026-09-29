/**
 * Unified LLM Client supporting Local Ollama and Groq Cloud.
 *
 * For Local Ollama:
 * First attempts to use the Backend Proxy at `${VITE_BIRD_API_URL}/llm/chat`
 * which bypasses all browser CORS and Private Network Access limitations
 * (especially when accessing the site via LAN IP like 192.168.x.x or different hostnames).
 * Falls back to direct browser fetch at `http://127.0.0.1:11434/v1/chat/completions`.
 */

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatOptions {
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
  json_mode?: boolean;
}

export async function chatCompletion(options: ChatOptions): Promise<string> {
  const provider = (import.meta.env.VITE_LLM_PROVIDER || "auto").toLowerCase();
  const configuredModel =
    import.meta.env.VITE_OLLAMA_MODEL ||
    import.meta.env.VITE_GROQ_MODEL ||
    "llama3.2:1b";
  const backendUrl = (import.meta.env.VITE_BIRD_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const ollamaUrl = (import.meta.env.VITE_OLLAMA_URL || "http://127.0.0.1:11434").replace(/\/$/, "");
  const groqApiKey = import.meta.env.VITE_GROQ_API_KEY || "";

  // Use Ollama if:
  // 1. Explicitly configured as "ollama"
  // 2. Model tag contains ":" (standard Ollama tag, e.g. "llama3.2:1b", "qwen2.5:7b")
  // 3. No Groq key is present
  const isOllama =
    provider === "ollama" ||
    configuredModel.includes(":") ||
    (!groqApiKey && provider !== "groq");

  if (isOllama) {
    const model = configuredModel.includes(":")
      ? configuredModel
      : import.meta.env.VITE_OLLAMA_MODEL || "llama3.2:1b";

    const payload = {
      model,
      messages: options.messages,
      temperature: options.temperature ?? 0.1,
      max_tokens: options.max_tokens ?? 4096,
      response_format: options.json_mode !== false ? { type: "json_object" } : undefined,
    };

    // 1. Try Backend Proxy first (Backend has CORS set to * and direct local access to Ollama)
    if (backendUrl) {
      try {
        const res = await fetch(`${backendUrl}/llm/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          const data = await res.json();
          return data.choices?.[0]?.message?.content?.trim() || "";
        }
      } catch (err) {
        console.warn("Backend /llm/chat proxy unreachable, attempting direct Ollama...", err);
      }
    }

    // 2. Try direct Ollama connection
    try {
      const res = await fetch(`${ollamaUrl}/v1/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.text();
        throw new Error(`Ollama ${res.status}: ${err.slice(0, 300)}`);
      }

      const data = await res.json();
      return data.choices?.[0]?.message?.content?.trim() || "";
    } catch (err: any) {
      if (err.message && err.message.startsWith("Ollama ")) {
        throw err;
      }
      throw new Error(`Cannot reach Ollama at ${ollamaUrl}. Ensure Ollama is running ('ollama serve').`);
    }
  }

  // Cloud Groq path
  const groqModel = configuredModel.includes(":")
    ? "openai/gpt-oss-20b"
    : configuredModel;

  try {
    const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${groqApiKey}`,
      },
      body: JSON.stringify({
        model: groqModel,
        messages: options.messages,
        temperature: options.temperature ?? 0.1,
        max_tokens: options.max_tokens ?? 4096,
        response_format: options.json_mode !== false ? { type: "json_object" } : undefined,
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      console.warn(`Groq error (${res.status}), attempting local Ollama fallback...`);

      // Try local fallback via backend or direct
      try {
        const fbRes = await fetch(`${backendUrl}/llm/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: "llama3.2:1b",
            messages: options.messages,
            temperature: options.temperature ?? 0.1,
            max_tokens: options.max_tokens ?? 4096,
            response_format: options.json_mode !== false ? { type: "json_object" } : undefined,
          }),
        });
        if (fbRes.ok) {
          const fbData = await fbRes.json();
          return fbData.choices?.[0]?.message?.content?.trim() || "";
        }
      } catch {}

      throw new Error(`Groq ${res.status}: ${err.slice(0, 300)}`);
    }

    const data = await res.json();
    return data.choices?.[0]?.message?.content?.trim() || "";
  } catch (err: any) {
    // If network failure reaching Groq, attempt local fallback
    if (!err.message?.includes("Ollama")) {
      try {
        const fbRes = await fetch(`${backendUrl}/llm/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: "llama3.2:1b",
            messages: options.messages,
            temperature: options.temperature ?? 0.1,
            max_tokens: options.max_tokens ?? 4096,
            response_format: options.json_mode !== false ? { type: "json_object" } : undefined,
          }),
        });
        if (fbRes.ok) {
          const fbData = await fbRes.json();
          return fbData.choices?.[0]?.message?.content?.trim() || "";
        }
      } catch {}
    }
    throw err;
  }
}
