/**
 * Fetch-based SSE reader used by every PRISM stream (analysis, LLM
 * extraction, LIME, simulation). Unlike EventSource it supports POST,
 * custom headers, and AbortController; heartbeat comment lines are
 * filtered out before the handler sees anything.
 */

export interface SSEHandle {
  abort: () => void;
  done: Promise<void>;
}

export function openSSE(
  url: string,
  onEvent: (data: any) => void,
  options?: {
    method?: "GET" | "POST";
    body?: unknown;
    onError?: (error: Error) => void;
    onClose?: () => void;
  }
): SSEHandle {
  const controller = new AbortController();

  const done = (async () => {
    try {
      const res = await fetch(url, {
        method: options?.method ?? "GET",
        headers: options?.body !== undefined ? { "Content-Type": "application/json" } : undefined,
        body: options?.body !== undefined ? JSON.stringify(options.body) : undefined,
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(`SSE connection failed (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const dispatch = (frame: string) => {
        for (const line of frame.split("\n")) {
          if (!line.startsWith("data:")) continue; // comments/heartbeats
          const payload = line.slice(5).trim();
          if (!payload) continue;
          try {
            onEvent(JSON.parse(payload));
          } catch {
            // malformed frame — skip
          }
        }
      };

      while (true) {
        const { done: finished, value } = await reader.read();
        if (finished) break;
        // Normalise CRLF so "\r\n\r\n" frame separators are recognised too.
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

        // SSE frames are separated by a blank line.
        let sep: number;
        while ((sep = buffer.indexOf("\n\n")) !== -1) {
          dispatch(buffer.slice(0, sep));
          buffer = buffer.slice(sep + 2);
        }
      }
      // A final frame without a trailing blank line is still a complete event.
      buffer += decoder.decode();
      if (buffer.trim()) dispatch(buffer);
      options?.onClose?.();
    } catch (error) {
      if (controller.signal.aborted) {
        options?.onClose?.();
        return;
      }
      options?.onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  })();

  return { abort: () => controller.abort(), done };
}
