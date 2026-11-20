import { authenticatedFetch } from './authenticatedFetch';

declare const process: { env: { EXPO_PUBLIC_API_BASE_URL?: string } };
const BASE_URL = `${process.env.EXPO_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8002'}/api/v1`;

export type CalendarItem = {
  type: 'PERSONAL' | 'CLASS' | 'EVENT' | 'BUSY';
  id?: number;
  title?: string;
  start_at: string;
  end_at: string;
  is_all_day?: boolean;
  location?: string | null;
};

export type CreatePersonalEntry = {
  title: string;
  description?: string | null;
  location?: string | null;
  start_at: string;
  end_at: string;
  is_all_day?: boolean;
  color?: string | null;
  visibility_override?: 'HIDDEN' | 'BUSY' | null;
};

export type FriendUser = {
  id: number;
  display_name: string;
  profile_image_url: string | null;
};

export type Friend = {
  user: FriendUser;
  sharing: {
    class: 'HIDDEN' | 'BUSY' | 'DETAILS';
    personal: 'HIDDEN' | 'BUSY' | 'DETAILS';
    event: 'HIDDEN' | 'BUSY' | 'DETAILS';
  };
};

export type FriendRequest = {
  id: number;
  from_user: FriendUser;
  to_user: FriendUser;
  status: 'PENDING' | 'ACCEPTED' | 'DECLINED';
  created_at: string;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await authenticatedFetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> | undefined),
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type UserSearchResult = FriendUser & {
  friend_status: 'NONE' | 'REQUESTED' | 'RECEIVED' | 'FRIENDS';
};

export type UserCalendar = {
  user_id: number;
  items: CalendarItem[];
};

export const calendarFriendsApi = {
  getMyCalendar: (start: string, end: string) => {
    const query = new URLSearchParams({ start, end });
    return request<CalendarItem[]>(`/calendar?${query.toString()}`);
  },

  createPersonalEntry: (entry: CreatePersonalEntry) =>
    request<CalendarItem>('/entries', {
      method: 'POST',
      body: JSON.stringify(entry),
    }),

  getPersonalEntry: (entryId: number) =>
    request<CreatePersonalEntry & { id: number; kind: string }>(
      `/entries/${entryId}`
    ),

  updatePersonalEntry: (
    entryId: number,
    changes: Partial<CreatePersonalEntry>
  ) =>
    request<CalendarItem>(`/entries/${entryId}`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }),

  deletePersonalEntry: (entryId: number) =>
    request<void>(`/entries/${entryId}`, { method: 'DELETE' }),

  searchUsers: (query: string) =>
    request<UserSearchResult[]>(`/users/search?q=${encodeURIComponent(query.trim())}`),

  getFriends: () =>
    request<Friend[]>('/friends'),

  getIncomingRequests: () =>
    request<FriendRequest[]>('/friends/requests?direction=incoming'),

  getOutgoingRequests: () =>
    request<FriendRequest[]>('/friends/requests?direction=outgoing'),

  sendFriendRequest: (toUserId: number) =>
    request<FriendRequest>('/friends/requests', {
      method: 'POST',
      body: JSON.stringify({ to_user_id: toUserId }),
    }),

  acceptFriendRequest: (requestId: number) =>
    request<FriendRequest>(`/friends/requests/${requestId}/accept`, {
      method: 'POST',
    }),

  declineFriendRequest: (requestId: number) =>
    request<FriendRequest>(`/friends/requests/${requestId}/decline`, {
      method: 'POST',
    }),

  cancelFriendRequest: (requestId: number) =>
    request<void>(`/friends/requests/${requestId}`, { method: 'DELETE' }),

  removeFriend: (userId: number) =>
    request<void>(`/friends/${userId}`, { method: 'DELETE' }),

  getFriendSharing: (userId: number) =>
    request<Friend['sharing']>(`/friends/${userId}/sharing`),

  updateFriendSharing: (
    userId: number,
    changes: Partial<Friend['sharing']>
  ) =>
    request<unknown>(`/friends/${userId}/sharing`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }),

  getCalendarOverlay: (
    userIds: number[],
    start: string,
    end: string
  ) => {
    const params = new URLSearchParams({
      user_ids: userIds.join(','),
      start,
      end,
    });

    return request<UserCalendar[]>(
      `/calendar/overlay?${params.toString()}`
    );
  },

  getFriendCalendar: (userId: number, start: string, end: string) => {
    const query = new URLSearchParams({ start, end });
    return request<CalendarItem[]>(
      `/users/${userId}/calendar?${query.toString()}`
    );
  },
};
