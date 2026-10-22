export type CampusEvent = {
  id: number; title: string; start_at: string; end_at: string;
  location_name: string | null; is_all_day: boolean; status: 'ACTIVE' | 'CANCELLED';
};
// No /users/me endpoint yet; replace with the signed-in user once auth exists.
export const demoUser = { display_name: 'Joanna', initials: 'JC' };
