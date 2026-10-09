const timeZone = 'America/New_York';
const dayKey = (date: Date) => new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
export function dateLabel(iso: string, now: Date) {
  const date = new Date(iso);
  if (dayKey(date) === dayKey(now)) return 'TODAY';
  const weekday = new Intl.DateTimeFormat('en-US', { timeZone, weekday: 'short' }).format(date);
  const month = new Intl.DateTimeFormat('en-US', { timeZone, month: 'short' }).format(date);
  const day = new Intl.DateTimeFormat('en-US', { timeZone, day: 'numeric' }).format(date);
  return `${weekday} ${month}\n${day}`.toUpperCase();
}
export const eventTime = (iso: string) => new Intl.DateTimeFormat('en-US', { timeZone, hour: 'numeric', minute: '2-digit' }).format(new Date(iso));
export const headerDate = (date: Date) => new Intl.DateTimeFormat('en-US', { timeZone, weekday: 'long', month: 'short', day: 'numeric' }).format(date);
export function greeting(date: Date) {
  const hour = Number(new Intl.DateTimeFormat('en-US', { timeZone, hour: 'numeric', hourCycle: 'h23' }).format(date));
  return hour < 12 ? 'Good morning,' : hour < 18 ? 'Good afternoon,' : 'Good evening,';
}
