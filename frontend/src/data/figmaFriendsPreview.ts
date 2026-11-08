import { useSyncExternalStore } from 'react';

// Figma-only example users. Never pass these string IDs to Backend APIs.
export type PreviewUser = {
  id: string;
  name: string;
  email: string;
  state: 'friend' | 'available';
  color: string;
};

export const FIGMA_FRIENDS_PREVIEW = true;
export const FIGMA_USERS: PreviewUser[] = [
  { id: 'maya', name: 'Maya Chen', email: 'maya.chen@nyu.edu', state: 'friend', color: '#E4EDF3' },
  { id: 'leo', name: 'Leo Martinez', email: 'leo.martinez@nyu.edu', state: 'friend', color: '#F4E9E2' },
  { id: 'priya', name: 'Priya Shah', email: 'priya.shah@nyu.edu', state: 'friend', color: '#E5F0EB' },
  { id: 'sarah', name: 'Sarah Lee', email: 'sarah.lee@nyu.edu', state: 'available', color: '#F1E5EB' },
  { id: 'daniel', name: 'Daniel Park', email: 'daniel.park@nyu.edu', state: 'available', color: '#F2EDE0' },
  { id: 'emily', name: 'Emily Chen', email: 'emily.chen@nyu.edu', state: 'available', color: '#E3F0F1' },
  { id: 'alex', name: 'Alex Kim', email: 'alex.kim@nyu.edu', state: 'available', color: '#E5EEF5' },
  { id: 'michelle', name: 'Michelle Wang', email: 'michelle.wang@nyu.edu', state: 'available', color: '#F2E9E5' },
];

// Simple in-memory store so the two screens agree on preview removals.
// It is reset on full JS reload and never touches the actual account.
let hidden: string[] = [];
const listeners = new Set<() => void>();
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
};
const getSnapshot = () => hidden;
export const useHiddenPreviewFriends = () => useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
export function hidePreviewFriend(id: string) {
  if (hidden.includes(id)) return;
  hidden = [...hidden, id];
  listeners.forEach(listener => listener());
}
