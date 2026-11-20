import { authApi } from './authApi';
import { clearSession, getSession, saveSession } from './authSession';

// A single refresh in flight prevents rotating the same refresh token twice.
let refreshInFlight: Promise<string | null> | null = null;

async function currentToken(): Promise<string | null> {
  const session = await getSession();
  return session?.access_token ?? null;
}

async function rotateToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const session = await getSession();
      if (!session?.refresh_token) return null;
      try {
        const updated = await authApi.refresh(session.refresh_token);
        await saveSession(updated);
        return updated.access_token;
      } catch (error) {
        // Keep the stored session through transient network failures.
        // A rejected refresh token requires a new login.
        if (error instanceof Error && /401|invalid.refresh|log in again/i.test(error.message)) {
          await clearSession();
        }
        throw error;
      }
    })().finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

export async function authenticatedFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = await currentToken();
  if (!token) throw new Error('Please log in again.');
  const send = (accessToken: string) => fetch(url, {
    ...options,
    headers: {
      ...(options.headers as Record<string, string> | undefined),
      Authorization: `Bearer ${accessToken}`,
    },
  });
  let response = await send(token);
  if (response.status === 401) {
    const renewed = await rotateToken();
    if (!renewed) throw new Error('Your session has expired. Please log in again.');
    response = await send(renewed);
  }
  return response;
}
