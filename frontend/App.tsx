import { useCallback, useEffect, useState } from 'react';
import { StatusBar, View, Text, ScrollView, StyleSheet, ActivityIndicator, Pressable, RefreshControl } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { BottomTabBar } from './src/components/BottomTabBar';
import { EventItem } from './src/components/EventItem';
import { CampusEvent, demoUser } from './src/data/events';
import { greeting, headerDate } from './src/date';
import { createApi } from './src/services/api';
const API_URL = process.env.EXPO_PUBLIC_API_URL;
const api = createApi(API_URL ?? '', () => undefined);
const WINDOW_DAYS = 14;
export default function App() {
  const [now, setNow] = useState(() => new Date());
  const [events, setEvents] = useState<CampusEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    const start = new Date();
    const end = new Date(start.getTime() + WINDOW_DAYS * 24 * 60 * 60 * 1000);
    try {
      if (!API_URL) throw new Error('EXPO_PUBLIC_API_URL is not set.');
      const page = await api.events(start, end, undefined, signal);
      setNow(start);
      setEvents(page.items);
      setError(null);
    } catch (e) {
      if (signal?.aborted) return;
      setError(e instanceof Error ? e.message : 'Could not load events.');
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).finally(() => setLoading(false));
    return () => controller.abort();
  }, [load]);
  const retry = () => { setLoading(true); load().finally(() => setLoading(false)); };
  const refresh = () => { setRefreshing(true); load().finally(() => setRefreshing(false)); };
  return <SafeAreaProvider>
    <StatusBar barStyle="dark-content" backgroundColor="#FFFFFF" />
    <SafeAreaView style={styles.screen} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.content} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
        <View style={styles.header}>
          <View style={styles.heading}>
            <Text style={styles.date}>{headerDate(now)}</Text>
            <Text style={styles.greeting}>{greeting(now)}{'\n'}{demoUser.display_name}</Text>
          </View>
          <View style={styles.avatar} accessibilityLabel={`${demoUser.display_name}'s avatar`}><Text style={styles.initials}>{demoUser.initials}</Text></View>
        </View>
        <Text style={styles.section}>CAMPUS EVENTS</Text>
        {loading ? <ActivityIndicator style={styles.status} color="#929DB0" />
          : error ? <View style={styles.status}>
            <Text style={styles.message}>{error}</Text>
            <Pressable accessibilityRole="button" onPress={retry} style={({ pressed }) => ({ opacity: pressed ? 0.55 : 1 })}><Text style={styles.retry}>Try again</Text></Pressable>
          </View>
          : events.length === 0 ? <Text style={[styles.status, styles.message]}>No events in the next {WINDOW_DAYS} days.</Text>
          : events.map((event, index) => <EventItem key={event.id} event={event} now={now} last={index === events.length - 1} />)}
      </ScrollView>
      <BottomTabBar />
    </SafeAreaView>
  </SafeAreaProvider>;
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { flexGrow: 1, paddingHorizontal: 22, paddingTop: 14, paddingBottom: 24 },
  header: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
  heading: { flex: 1, paddingRight: 12 },
  date: { color: '#929DB0', fontSize: 13, lineHeight: 18, fontWeight: '500' },
  greeting: { fontSize: 24, lineHeight: 32, fontWeight: '700', color: '#111111', marginTop: 4 },
  avatar: { height: 38, width: 38, borderRadius: 19, backgroundColor: '#111111', alignItems: 'center', justifyContent: 'center' },
  initials: { fontSize: 12, color: '#FFFFFF', fontWeight: '600' },
  section: { fontSize: 11, lineHeight: 16, fontWeight: '600', letterSpacing: 1, color: '#929DB0', marginTop: 24, marginBottom: 8 },
  status: { marginTop: 24, alignItems: 'center', gap: 8 },
  message: { fontSize: 13, lineHeight: 18, color: '#929DB0', textAlign: 'center' },
  retry: { fontSize: 13, fontWeight: '600', color: '#111111' },
});
