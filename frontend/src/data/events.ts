export type CampusEvent = {
  id: number; title: string; start_at: string; end_at: string;
  location_name: string | null; is_all_day: boolean;
};
export type HomeEvent = CampusEvent & { designDate?: string };
export const demoNow = new Date('2026-09-30T18:00:00Z');
export const demoUser = { display_name: 'Joanna', initials: 'JC' };
export const demoEvents: HomeEvent[] = [
  { id: 1, title: 'NYU Career Fair', start_at: '2026-09-30T20:00:00Z', end_at: '2026-09-30T21:00:00Z', location_name: 'Palladium', is_all_day: false, designDate: 'TODAY' },
  { id: 2, title: 'Guest Lecture: AI & Design', start_at: '2026-10-02T21:00:00Z', end_at: '2026-10-02T22:00:00Z', location_name: 'Tisch Hall', is_all_day: false, designDate: 'THU OCT\n2' },
  { id: 3, title: 'NYU Club Fair', start_at: '2026-10-06T16:00:00Z', end_at: '2026-10-06T17:00:00Z', location_name: 'Kimmel Center', is_all_day: false, designDate: 'MON OCT\n6' },
];
