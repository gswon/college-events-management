
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { PersonalEvent } from '../screens/AddEventScreen';

const STORAGE_KEY = '@nyu-event-calendar/personal-events';

export async function loadPersonalEvents(): Promise<PersonalEvent[]> {
  const stored = await AsyncStorage.getItem(STORAGE_KEY);

  if (!stored) {
    return [];
  }

  const parsed: unknown = JSON.parse(stored);

  if (!Array.isArray(parsed)) {
    throw new Error('Invalid saved calendar data.');
  }

  return parsed as PersonalEvent[];
}

export async function savePersonalEvent(
  event: PersonalEvent
): Promise<PersonalEvent[]> {
  const currentEvents = await loadPersonalEvents();

  const updatedEvents = [...currentEvents, event];

  await AsyncStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(updatedEvents)
  );

  return updatedEvents;
}
