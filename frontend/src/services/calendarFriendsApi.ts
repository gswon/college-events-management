
const BASE_URL = 'http://127.0.0.1:8001/api/v1';

// LOCAL DEVELOPMENT ONLY.
// The backend currently uses X-User-Id instead of production authentication.
const DEV_USER_ID = 1;

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

async function request<T>(
  path: string,
  options: RequestInit = {},
  userId: number = DEV_USER_ID
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-User-Id': String(userId),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.error?.message ?? `Request failed (${response.status})`
    );
  }

  return response.json() as Promise<T>;
}

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

  deletePersonalEntry: async (entryId: number): Promise<void> => {
    const response = await fetch(`${BASE_URL}/entries/${entryId}`, {
      method: 'DELETE',
      headers: {
        Accept: 'application/json',
        'X-User-Id': String(DEV_USER_ID),
      },
    });

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(
        body?.error?.message ?? `Delete failed (${response.status})`
      );
    }
  },

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

  cancelFriendRequest: async (requestId: number): Promise<void> => {
    const response = await fetch(
      `${BASE_URL}/friends/requests/${requestId}`,
      {
        method: 'DELETE',
        headers: {
          Accept: 'application/json',
          'X-User-Id': String(DEV_USER_ID),
        },
      }
    );

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(
        body?.error?.message ??
          `Failed to cancel request (${response.status})`
      );
    }
  },

  removeFriend: async (userId: number): Promise<void> => {
    const response = await fetch(`${BASE_URL}/friends/${userId}`, {
      method: 'DELETE',
      headers: {
        Accept: 'application/json',
        'X-User-Id': String(DEV_USER_ID),
      },
    });

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(
        body?.error?.message ??
          `Failed to remove friend (${response.status})`
      );
    }
  },

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
