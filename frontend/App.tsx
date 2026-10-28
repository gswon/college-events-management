import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { SafeAreaProvider, SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { CampusEvent } from './src/data/events';
import { createApi } from './src/services/api';

// Keep the same API configuration you were using previously.
const api = createApi('http://127.0.0.1:8000', () => undefined);

type ApiEvent = CampusEvent & {
  status?: 'ACTIVE' | 'CANCELLED' | 'HIDDEN';
  category?: string | null;
  end_at?: string | null;
};
type Filter = 'All Events' | 'Career' | 'Social' | 'Academic' | 'Athletics' | 'Other';
const filters: Filter[] = ['All Events', 'Career', 'Social', 'Academic', 'Athletics', 'Other'];

function dayStart(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function validDate(value: unknown): Date | null {
  if (typeof value !== 'string' && !(value instanceof Date)) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function prettyDate(date: Date, weekday = true) {
  return new Intl.DateTimeFormat('en-US', {
    ...(weekday ? { weekday: 'long' as const } : {}),
    month: 'long',
    day: 'numeric',
  }).format(date);
}

function headingDate(date: Date) {
  return prettyDate(date);
}

function greeting(date: Date) {
  const hour = date.getHours();
  if (hour < 12) return 'Good morning,';
  if (hour < 17) return 'Good afternoon,';
  return 'Good evening,';
}

function getCategory(event: ApiEvent): Exclude<Filter, 'All Events'> {
  const raw = String(event.category ?? '').toLowerCase();
  const title = event.title.toLowerCase();
  const value = `${raw} ${title}`;
  if (/career|job|recruit|intern|networking|employ/.test(value)) return 'Career';
  if (/sport|athlet|soccer|basketball|volleyball|tennis|game vs|match/.test(value)) return 'Athletics';
  if (/academic|lecture|research|seminar|workshop|faculty|study|science|ai guest/.test(value)) return 'Academic';
  if (/social|party|grooves|mixer|community|coffee chat|club/.test(value)) return 'Social';
  return 'Other';
}

function eventTime(event: ApiEvent) {
  if (event.is_all_day) return 'All day';
  const start = validDate(event.start_at);
  if (!start) return 'Time TBA';
  const formatter = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' });
  const end = validDate(event.end_at);
  if (!end || end.getTime() <= start.getTime()) return formatter.format(start);
  return `${formatter.format(start)}–${formatter.format(end)}`;
}

function groupLabel(date: Date, now: Date) {
  const dayDiff = Math.round((dayStart(date).getTime() - dayStart(now).getTime()) / 86400000);
  if (dayDiff === 0) return 'Today';
  if (dayDiff === 1) return 'Tomorrow';
  return prettyDate(date, false);
}

function EventCard({ event }: { event: ApiEvent }) {
  const category = getCategory(event);
  const isCancelled = event.status === 'CANCELLED';
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${event.title}, ${category}`}
      onPress={() => Alert.alert(event.title, `${eventTime(event)}\n${event.location_name || 'Location TBA'}`)}
      style={({ pressed }) => [styles.eventRow, pressed && { opacity: 0.6 }]}
    >
      <View style={styles.eventContent}>
        <Text style={styles.eventTitle}>{isCancelled ? `[Cancelled] ${event.title}` : event.title}</Text>
        <View style={styles.categoryTag}><Text style={styles.categoryText}>{category}</Text></View>
        <Text style={styles.eventTime}>{eventTime(event)}</Text>
        <Text style={styles.eventLocation}>{event.location_name || 'Location TBA'}</Text>
      </View>
      <Feather name="chevron-right" size={22} color="#B0B0B5" />
    </Pressable>
  );
}

function BottomNavigation() {
  const { bottom } = useSafeAreaInsets();
  const tabs = [
    { label: 'Home', icon: 'home' },
    { label: 'Calendar', icon: 'calendar' },
    { label: 'Profile', icon: 'user' },
  ] as const;
  return (
    <View style={[styles.tabBar, { paddingBottom: Math.max(bottom, 10) }]}>
      {tabs.map(tab => {
        const selected = tab.label === 'Home';
        return (
          <Pressable
            key={tab.label}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            style={styles.tab}
            onPress={() => {
              if (!selected) Alert.alert(tab.label, `${tab.label} screen is coming next.`);
            }}
          >
            <Feather name={tab.icon} size={25} color={selected ? '#171717' : '#B6B6BA'} />
            <Text style={[styles.tabText, selected && styles.selectedTabText]}>{tab.label}</Text>
            <View style={[styles.tabDot, selected && styles.selectedTabDot]} />
          </Pressable>
        );
      })}
    </View>
  );
}

export default function App() {
  const [now, setNow] = useState(() => new Date());
  const [events, setEvents] = useState<ApiEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('All Events');
  const [filterOpen, setFilterOpen] = useState(false);
  const activeRequest = useRef<AbortController | null>(null);
  const range = useRef<{ start: Date; end: Date } | null>(null);

  async function loadEvents(mode: 'initial' | 'refresh' | 'more') {
    if (activeRequest.current || (mode === 'more' && !nextCursor)) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    setError(null);
    setLoading(mode === 'initial');
    setRefreshing(mode === 'refresh');
    setLoadingMore(mode === 'more');

    if (mode !== 'more') {
      const start = dayStart(new Date());
      const end = new Date(start.getTime() + 31 * 86400000);
      range.current = { start, end };
      setNow(new Date());
    }
    const currentRange = range.current!;
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const page = await api.events(
        currentRange.start,
        currentRange.end,
        mode === 'more' ? nextCursor ?? undefined : undefined,
        controller.signal,
      );
      const incoming = page.items as ApiEvent[];
      setEvents(previous => {
        if (mode !== 'more') return incoming;
        const unique = new Map(previous.map(event => [event.id, event]));
        incoming.forEach(event => unique.set(event.id, event));
        return [...unique.values()];
      });
      setNextCursor(page.next_cursor);
    } catch (err) {
      if (activeRequest.current !== controller) return;
      setError(controller.signal.aborted
        ? 'The request timed out. Please try again.'
        : err instanceof Error ? err.message : 'Unable to load events.');
    } finally {
      clearTimeout(timeout);
      if (activeRequest.current === controller) {
        activeRequest.current = null;
        setLoading(false);
        setRefreshing(false);
        setLoadingMore(false);
      }
    }
  }

  useEffect(() => {
    void loadEvents('initial');
    return () => {
      const controller = activeRequest.current;
      activeRequest.current = null;
      controller?.abort();
    };
  }, []);

  const from = dayStart(now).getTime();
  const until = from + 31 * 86400000;
  const visible = events
    .filter(event => event.status !== 'HIDDEN')
    .filter(event => {
      const date = validDate(event.start_at);
      return date !== null && date.getTime() >= from && date.getTime() < until;
    })
    .filter(event => filter === 'All Events' || getCategory(event) === filter)
    .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime());
  const grouped: { key: string; date: Date; items: ApiEvent[] }[] = [];
  visible.forEach(event => {
    const date = validDate(event.start_at)!;
    const key = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
    const last = grouped[grouped.length - 1];
    if (last?.key === key) last.items.push(event);
    else grouped.push({ key, date, items: [event] });
  });

  return (
    <SafeAreaProvider>
      <StatusBar barStyle="dark-content" backgroundColor="#FFFFFF" />
      <SafeAreaView style={styles.screen} edges={['top', 'left', 'right']}>
        <ScrollView
  style={styles.scroll}
  contentContainerStyle={styles.scrollContent}
  onScrollBeginDrag={() => console.log('SCROLL STARTED')}
  refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void loadEvents('refresh')} />}
>
          <View style={styles.topHeader}>
            <View style={styles.greetingWrap}>
              <Text style={styles.topDate}>{headingDate(now)}</Text>
              <Text style={styles.greeting}>{greeting(now)}{'\n'}Welcome to NYU</Text>
            </View>
            <View style={styles.avatar}><Text style={styles.avatarText}>NYU</Text></View>
          </View>

          <View style={styles.sectionHeader}>
            <View style={styles.sectionHeading}>
              <Text style={styles.eyebrow}>CAMPUS EVENTS</Text>
              <Text style={styles.sectionTitle}>Upcoming Events</Text>
            </View>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Filter events: ${filter}`}
              onPress={() => setFilterOpen(value => !value)}
              style={styles.filterButton}
            >
              <Text style={styles.filterButtonText}>{filter}</Text>
              <Feather name={filterOpen ? 'chevron-up' : 'chevron-down'} size={18} color="#6C6C73" />
            </Pressable>
          </View>

          {filterOpen && (
            <View style={styles.filterList}>
              {filters.map(option => (
                <Pressable
                  key={option}
                  style={styles.filterOption}
                  onPress={() => { setFilter(option); setFilterOpen(false); }}
                >
                  <Text style={[styles.filterOptionText, filter === option && styles.filterOptionSelected]}>{option}</Text>
                  {filter === option && <Feather name="check" size={18} color="#57068C" />}
                </Pressable>
              ))}
            </View>
          )}

          <View style={styles.sectionRule} />

          {loading && (
            <View style={styles.message}><ActivityIndicator color="#57068C" /><Text style={styles.messageText}>Loading events…</Text></View>
          )}
          {error && (
            <View style={styles.message}>
              <Text style={styles.error}>{error}</Text>
              <Pressable style={styles.retryButton} onPress={() => void loadEvents('refresh')}><Text style={styles.retryText}>Try again</Text></Pressable>
            </View>
          )}
          {!loading && !error && grouped.length === 0 && (
            <Text style={styles.emptyText}>No upcoming events found for {filter === 'All Events' ? 'the next 30 days' : filter.toLowerCase()}.</Text>
          )}

          {!loading && !error && grouped.map(group => (
            <View key={group.key} style={styles.dayGroup}>
              <View style={styles.dayHeader}>
                <Text style={styles.dayHeading}>{groupLabel(group.date, now)}</Text>
                <Text style={styles.dayDate}>{prettyDate(group.date)}</Text>
              </View>
              {group.items.map(event => <EventCard key={event.id} event={event} />)}
            </View>
          ))}

          {nextCursor && !loading && !error && (
            <Pressable
              style={styles.loadMoreButton}
              disabled={loadingMore || refreshing}
              onPress={() => void loadEvents('more')}
            >
              {loadingMore ? <ActivityIndicator color="#57068C" /> : <Text style={styles.loadMoreText}>Load more events</Text>}
            </Pressable>
          )}
        </ScrollView>
        <BottomNavigation />
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 20, paddingTop: 24, paddingBottom: 36 },
  topHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  greetingWrap: { flex: 1, paddingRight: 8 },
  topDate: { fontSize: 15, lineHeight: 22, color: '#9797A0', fontWeight: '500' },
  greeting: { fontSize: 29, lineHeight: 36, color: '#1C1C1E', fontWeight: '700', marginTop: 12, letterSpacing: -0.8 },
  avatar: { width: 48, height: 48, borderRadius: 24, backgroundColor: '#171717', alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: '#FFFFFF', fontWeight: '600', fontSize: 13 },
  sectionHeader: { marginTop: 52, flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: 8 },
  sectionHeading: { flexShrink: 1 },
  eyebrow: { color: '#92929D', fontSize: 11, fontWeight: '700', letterSpacing: 1.7, marginBottom: 8 },
  sectionTitle: { color: '#171717', fontSize: 27, lineHeight: 34, fontWeight: '700', letterSpacing: -0.9 },
  filterButton: { minWidth: 113, paddingHorizontal: 12, height: 40, borderWidth: 1, borderColor: '#E1E1E6', borderRadius: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  filterButtonText: { fontSize: 12, color: '#3B3B40', fontWeight: '500', flexShrink: 1 },
  filterList: { borderWidth: 1, borderColor: '#E7E7EB', borderRadius: 10, marginTop: 12, overflow: 'hidden' },
  filterOption: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 15, paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#EBEBEF' },
  filterOptionText: { color: '#424247', fontSize: 14 },
  filterOptionSelected: { color: '#57068C', fontWeight: '700' },
  sectionRule: { borderBottomWidth: 1, borderBottomColor: '#EBEBEE', marginTop: 24 },
  dayGroup: { marginTop: 33 },
  dayHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderBottomWidth: 1, borderBottomColor: '#EBEBEE', paddingBottom: 14 },
  dayHeading: { color: '#242428', fontSize: 19, fontWeight: '700' },
  dayDate: { color: '#9C9CA6', fontSize: 12 },
  eventRow: { minHeight: 135, paddingHorizontal: 2, paddingTop: 19, paddingBottom: 18, borderBottomWidth: 1, borderBottomColor: '#EBEBEE', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  eventContent: { flex: 1, paddingRight: 10 },
  eventTitle: { fontSize: 16, lineHeight: 22, color: '#242428', fontWeight: '600' },
  categoryTag: { borderWidth: 1, borderColor: '#E1E1E6', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, alignSelf: 'flex-start', marginTop: 8, marginBottom: 8 },
  categoryText: { color: '#85858D', fontSize: 11, lineHeight: 16 },
  eventTime: { fontSize: 13, color: '#484850', fontWeight: '500', marginBottom: 5 },
  eventLocation: { fontSize: 12, color: '#9C9CA6', lineHeight: 18 },
  tabBar: { flexDirection: 'row', backgroundColor: '#FFFFFF', borderTopWidth: 1, borderTopColor: '#EAEAEF', paddingTop: 12 },
  tab: { flex: 1, alignItems: 'center', gap: 6, paddingVertical: 4 },
  tabText: { fontSize: 12, color: '#9D9DA4' },
  selectedTabText: { color: '#1C1C1E', fontWeight: '600' },
  tabDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: 'transparent', marginTop: 1 },
  selectedTabDot: { backgroundColor: '#702099' },
  message: { alignItems: 'center', paddingVertical: 30, gap: 12 },
  messageText: { color: '#888891', fontSize: 13 },
  error: { color: '#B42318', textAlign: 'center', fontSize: 13 },
  retryButton: { paddingHorizontal: 16, paddingVertical: 10, backgroundColor: '#F4ECFA', borderRadius: 8 },
  retryText: { color: '#57068C', fontWeight: '600' },
  emptyText: { paddingTop: 36, color: '#92929D', fontSize: 14, textAlign: 'center' },
  loadMoreButton: { alignItems: 'center', padding: 16, marginTop: 14 },
  loadMoreText: { color: '#57068C', fontSize: 14, fontWeight: '600' },
});
