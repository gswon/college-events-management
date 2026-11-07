import AsyncStorage from '@react-native-async-storage/async-storage';

// Device-only prototype data. NOT an authenticated user profile or server update.
export type LocalProfile = {
  fullName: string;
  email: string;
  program: string;
};

const KEY = 'nyu-events/local-profile-draft/v1';

export async function loadLocalProfile(): Promise<LocalProfile | null> {
  const stored = await AsyncStorage.getItem(KEY);
  if (!stored) return null;
  try {
    const value: unknown = JSON.parse(stored);
    if (typeof value !== 'object' || value === null) return null;
    const obj = value as Record<string, unknown>;
    if (typeof obj.fullName !== 'string' || typeof obj.email !== 'string' || typeof obj.program !== 'string') return null;
    return { fullName: obj.fullName, email: obj.email, program: obj.program };
  } catch { return null; }
}

export async function saveLocalProfile(profile: LocalProfile): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(profile));
}
