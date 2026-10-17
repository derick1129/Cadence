/**
 * Client authentication helpers integrating with backend FastAPI /auth endpoints.
 */

export interface TokenResponse {
  access_token: string;
  token_type: string;
  refresh_token?: string | null;
}

export interface SignupPayload {
  email: string;
  password: string;
  organization_name?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

const BACKEND_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" ? "/api/backend" : "http://localhost:8000");

export async function signup(payload: SignupPayload): Promise<TokenResponse> {
  const res = await fetch(`${BACKEND_BASE}/auth/signup`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || "Failed to create account");
  }

  const data: TokenResponse = await res.json();
  if (typeof window !== "undefined" && data.access_token) {
    localStorage.setItem("cadence_token", data.access_token);
  }
  return data;
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  const res = await fetch(`${BACKEND_BASE}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || "Invalid email or password");
  }

  const data: TokenResponse = await res.json();
  if (typeof window !== "undefined" && data.access_token) {
    localStorage.setItem("cadence_token", data.access_token);
  }
  return data;
}

export function logout(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("cadence_token");
  }
}
