import { CampusEvent } from '../data/events';
export type Page<T> = { items: T[]; next_cursor: string | null };
export type User = { id: number; display_name: string; profile_image_url?: string | null };
// Pass the access token from the team's authentication flow. Do not hard-code it.
export function createApi(baseUrl: string, getAccessToken: () => string | undefined) {
  async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const token = getAccessToken();
    const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/v1${path}`, {
      headers: { Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
    }
    return response.json() as Promise<T>;
  }
  return {
    me: (signal?: AbortSignal) => get<User>('/users/me', signal),
    events: (start: Date, end: Date, cursor?: string, signal?: AbortSignal) => {
      const params = new URLSearchParams({ start: start.toISOString(), end: end.toISOString(), limit: '20' });
      if (cursor) params.set('cursor', cursor);
      return get<Page<CampusEvent>>(`/events?${params}`, signal);
    },
  };
}
