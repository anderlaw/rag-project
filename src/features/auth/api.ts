import { HttpError, requestJson } from "../../lib/http";
import type { CurrentUser, LoginRequest, LogoutResponse } from "./types";

const AUTH_BASE = "/api/v1/auth";

export function login(request: LoginRequest): Promise<CurrentUser> {
  return requestJson<CurrentUser>(`${AUTH_BASE}/login`, {
    method: "POST",
    body: JSON.stringify(request)
  });
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  try {
    return await requestJson<CurrentUser>(`${AUTH_BASE}/me`);
  } catch (error) {
    if (error instanceof HttpError && error.status === 401) {
      return null;
    }
    throw error;
  }
}

export function logout(): Promise<LogoutResponse> {
  return requestJson<LogoutResponse>(`${AUTH_BASE}/logout`, {
    method: "POST"
  });
}
