export class HttpError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "HttpError";
  }
}

export const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const requestInit = init
    ? {
        ...init,
        credentials: init.credentials ?? ("include" as RequestCredentials),
        headers: {
          ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
          ...init.headers
        }
      }
    : { credentials: "include" as RequestCredentials };
  const response = await fetch(resolveApiUrl(path), requestInit);

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new HttpError(message, response.status);
  }

  return (await response.json()) as T;
}

function resolveApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  const normalizedBaseURL = normalizeLocalApiBaseURL(baseURL).replace(/\/+$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBaseURL}${normalizedPath}`;
}

function normalizeLocalApiBaseURL(value: string): string {
  if (typeof window === "undefined") {
    return value;
  }
  try {
    const url = new URL(value);
    const pageHost = window.location.hostname;
    const localHosts = new Set(["localhost", "127.0.0.1"]);
    if (localHosts.has(url.hostname) && localHosts.has(pageHost)) {
      url.hostname = pageHost;
      return url.toString().replace(/\/$/, "");
    }
  } catch {
    return value;
  }
  return value;
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // Fall through to status text.
  }
  return response.statusText || `HTTP ${response.status}`;
}
