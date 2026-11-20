import * as SecureStore from 'expo-secure-store';
import { authApi, type AuthSession } from './authApi';

const SESSION_KEY = 'nyu_events_auth_session';

export async function saveSession(
  session: AuthSession
): Promise<void> {
  await SecureStore.setItemAsync(
    SESSION_KEY,
    JSON.stringify(session)
  );
}

export async function getSession(): Promise<AuthSession | null> {
  const stored = await SecureStore.getItemAsync(SESSION_KEY);

  if (!stored) {
    return null;
  }

  try {
    return JSON.parse(stored) as AuthSession;
  } catch {
    await SecureStore.deleteItemAsync(SESSION_KEY);
    return null;
  }
}

export async function clearSession(): Promise<void> {
  await SecureStore.deleteItemAsync(SESSION_KEY);
}

export async function refreshSession(): Promise<AuthSession | null> {
  const current = await getSession();

  if (!current?.refresh_token) {
    return null;
  }

  try {
    const updated = await authApi.refresh(current.refresh_token);
    await saveSession(updated);
    return updated;
  } catch (error) {
    if (error instanceof Error && /401|invalid.refresh|log in again/i.test(error.message)) {
      await clearSession();
    }
    throw error;
  }
}

export async function logoutSession(): Promise<void> {
  const session = await getSession();

  try {
    if (session?.access_token) {
      await authApi.logout(session.access_token);
    }
  } finally {
    await clearSession();
  }
}
