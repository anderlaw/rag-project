export class HttpError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "HttpError";
  }
}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const requestInit = init
    ? {
        ...init,
        headers: {
          ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
          ...init.headers
        }
      }
    : undefined;
  const response = await fetch(path, requestInit);

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new HttpError(message, response.status);
  }

  return (await response.json()) as T;
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
