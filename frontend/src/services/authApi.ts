declare const process: { env: { EXPO_PUBLIC_API_BASE_URL?: string } };

const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, '');

export type AuthUser = {
  id: number;
  email: string;
  display_name: string;
  profile_image_url?: string | null;
};

export type AuthSession = {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: AuthUser;
};

async function request<T>(
  path: string,
  body?: object,
  accessToken?: string
): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error('EXPO_PUBLIC_API_BASE_URL is not configured.');
  }

  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(accessToken
        ? { Authorization: `Bearer ${accessToken}` }
        : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      data?.error?.message ??
      `Authentication request failed (${response.status})`
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const authApi = {
  signup: (
    email: string,
    password: string,
    displayName: string
  ) =>
    request<{ email: string }>('/auth/signup', {
      email,
      password,
      display_name: displayName,
    }),

  verifyEmail: (email: string, code: string) =>
    request<AuthSession>('/auth/verify-email', {
      email,
      code,
    }),

  resendVerification: (email: string) =>
    request<void>('/auth/verify-email/resend', { email }),

  login: (email: string, password: string) =>
    request<AuthSession>('/auth/login', {
      email,
      password,
    }),

  refresh: (refreshToken: string) =>
    request<AuthSession>('/auth/refresh', {
      refresh_token: refreshToken,
    }),

  logout: (accessToken: string) =>
    request<void>('/auth/logout', undefined, accessToken),

  forgotPassword: (email: string) =>
    request<void>('/auth/password/forgot', { email }),

  resetPassword: (
    email: string,
    code: string,
    newPassword: string
  ) =>
    request<void>('/auth/password/reset', {
      email,
      code,
      new_password: newPassword,
    }),
};
