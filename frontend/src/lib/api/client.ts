const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export type ApiErrorBody = { detail: string };

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly body: ApiErrorBody) { super(body.detail); this.name = "ApiError"; }
}

export async function apiFetch<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(new URL(path, API_BASE_URL), { ...init, headers });
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;
    try { const body: unknown = await response.json(); if (typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string") detail = body.detail; } catch { /* Keep the normalized fallback. */ }
    throw new ApiError(response.status, { detail });
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
