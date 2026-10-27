/**
 * Typed HTTP client wrapper for backend control plane API.
 */

export class ApiError extends Error {
  code: string;
  status: number;
  details?: unknown;

  constructor(message: string, status: number, code: string = "API_ERROR", details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const BACKEND_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" ? "/api/backend" : "http://localhost:8000");

function getStorageToken(): string | null {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      return window.localStorage.getItem("cadence_token");
    }
    if (typeof localStorage !== "undefined" && typeof localStorage.getItem === "function") {
      return localStorage.getItem("cadence_token");
    }
  } catch {
    return null;
  }
  return null;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStorageToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const url = endpoint.startsWith("http") ? endpoint : `${BACKEND_BASE}${endpoint}`;
  const response = await fetch(url, { ...options, headers });

  if (response.status === 204) {
    return {} as T;
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errorInfo = (typeof data === "object" && data !== null && "error" in data) ? data.error : {};
    const detail = (typeof data === "object" && data !== null && "detail" in data) ? data.detail : undefined;
    const message = errorInfo?.message || detail || `Request failed with status ${response.status}`;
    const code = errorInfo?.code || "REQUEST_FAILED";
    throw new ApiError(message, response.status, code, errorInfo?.details);
  }

  return data as T;
}
