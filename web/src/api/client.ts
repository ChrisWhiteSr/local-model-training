const DEFAULT_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

export function getBaseUrl(): string {
  const v = localStorage.getItem('apiBase');
  return v || DEFAULT_BASE;
}

export function setBaseUrl(url: string) {
  localStorage.setItem('apiBase', url);
}

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(getBaseUrl() + path);
  if (!r.ok) throw new Error(`GET ${path} failed: ${r.status}`);
  return r.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: any): Promise<T> {
  const r = await fetch(getBaseUrl() + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {})
  });
  if (!r.ok) throw new Error(`POST ${path} failed: ${r.status}`);
  return r.json() as Promise<T>;
}

