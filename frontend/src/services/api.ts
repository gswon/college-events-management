import { CampusEvent } from '../data/events';
import { authenticatedFetch } from './authenticatedFetch';
export type Page<T> = { items: T[]; next_cursor: string | null };
export type User = { id: number; display_name: string; profile_image_url?: string | null };
export type EventCategory = {
  code: string;
  name: string;
  color: string | null;
};
// Pass the access token from the team's authentication flow. Do not hard-code it.
export function createApi(baseUrl: string, getAccessToken: () => string | undefined) {
  async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const response = await authenticatedFetch(`${baseUrl.replace(/\/$/, '')}/api/v1${path}`, {
      headers: { Accept: 'application/json' }, signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
    }
    return response.json() as Promise<T>;
  }
  return {
    me: (signal?: AbortSignal) => get<User>('/users/me', signal),
    categories: (signal?: AbortSignal) =>
      get<EventCategory[]>('/categories', signal),

    events: (
      start: Date,
      end: Date,
      cursor?: string,
      signal?: AbortSignal,
      category?: string,
    ) => {
      const params = new URLSearchParams({
        start: start.toISOString(),
        end: end.toISOString(),
        limit: '100',
      });

      if (cursor) params.set('cursor', cursor);
      if (category) params.set('category', category);

      return get<Page<CampusEvent>>(`/events?${params}`, signal);
    },
  };
}
