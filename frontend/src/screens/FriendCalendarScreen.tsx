
import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import {
  calendarFriendsApi,
  type CalendarItem,
} from '../services/calendarFriendsApi';

type Props = {
  friendId: number;
  friendName: string;
  onBack: () => void;
};

function formatDate(date: Date) {
  return date.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });
}

export default function FriendCalendarScreen({
  friendId,
  friendName,
  onBack,
}: Props) {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [items, setItems] = useState<CalendarItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCalendar = useCallback(async () => {
    setLoading(true);
    setError(null);

    const start = new Date(
      selectedDate.getFullYear(),
      selectedDate.getMonth(),
      selectedDate.getDate()
    );
    const end = new Date(
      selectedDate.getFullYear(),
      selectedDate.getMonth(),
      selectedDate.getDate() + 1
    );

    try {
      const result = await calendarFriendsApi.getFriendCalendar(
        friendId,
        start.toISOString(),
        end.toISOString()
      );
      setItems(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not load calendar.'
      );
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [friendId, selectedDate]);

  useEffect(() => {
    void loadCalendar();
  }, [loadCalendar]);

  function changeDay(offset: number) {
    setSelectedDate(
      new Date(
        selectedDate.getFullYear(),
        selectedDate.getMonth(),
        selectedDate.getDate() + offset
      )
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Pressable onPress={onBack} accessibilityLabel="Back to Friends">
          <Feather name="arrow-left" size={24} color="#171717" />
        </Pressable>
        <Text style={styles.title}>{friendName}</Text>
        <Pressable onPress={() => void loadCalendar()} accessibilityLabel="Refresh calendar">
          <Feather name="refresh-cw" size={20} color="#171717" />
        </Pressable>
      </View>

      <Text style={styles.subtitle}>Shared Calendar</Text>

      <View style={styles.dateSelector}>
        <Pressable onPress={() => changeDay(-1)} accessibilityLabel="Previous day">
          <Feather name="chevron-left" size={24} color="#171717" />
        </Pressable>
        <Text style={styles.dateText}>{formatDate(selectedDate)}</Text>
        <Pressable onPress={() => changeDay(1)} accessibilityLabel="Next day">
          <Feather name="chevron-right" size={24} color="#171717" />
        </Pressable>
      </View>

      <Text style={styles.sectionTitle}>SHARED SCHEDULE</Text>

      {loading ? (
        <ActivityIndicator color="#57068C" style={styles.loader} />
      ) : error ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyText}>{error}</Text>
          <Pressable onPress={() => void loadCalendar()}>
            <Text style={styles.retry}>Try again</Text>
          </Pressable>
        </View>
      ) : items.length === 0 ? (
        <Text style={styles.emptyText}>No shared events for this day.</Text>
      ) : (
        items.map((item, index) => (
          <View
            key={`${item.type}-${item.id ?? 'busy'}-${index}`}
            style={styles.eventCard}
          >
            <Text style={styles.eventTime}>
              {item.is_all_day
                ? 'All day'
                : `${formatTime(item.start_at)} – ${formatTime(item.end_at)}`}
            </Text>
            <Text style={styles.eventTitle}>
              {item.type === 'BUSY' ? 'Busy' : item.title ?? 'Event'}
            </Text>
            {item.type !== 'BUSY' && item.location ? (
              <Text style={styles.eventLocation}>{item.location}</Text>
            ) : null}
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { paddingHorizontal: 24, paddingTop: 20, paddingBottom: 40 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  title: { fontSize: 21, fontWeight: '700', color: '#171717' },
  subtitle: { marginTop: 26, color: '#9999A5', fontSize: 14 },
  dateSelector: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 30,
    marginBottom: 36,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#EBEBEB',
  },
  dateText: { fontSize: 17, fontWeight: '600', color: '#171717' },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.5,
    color: '#9999A5',
    marginBottom: 18,
  },
  loader: { marginTop: 30 },
  emptyContainer: { alignItems: 'center', marginTop: 30 },
  emptyText: { color: '#9999A5', fontSize: 14, marginTop: 20 },
  retry: { color: '#57068C', fontWeight: '600', marginTop: 14 },
  eventCard: {
    borderLeftWidth: 4,
    borderLeftColor: '#E7D8F0',
    paddingLeft: 16,
    paddingVertical: 13,
    marginBottom: 16,
  },
  eventTime: { color: '#9999A5', fontSize: 13 },
  eventTitle: {
    marginTop: 7,
    fontSize: 17,
    fontWeight: '600',
    color: '#171717',
  },
  eventLocation: { marginTop: 6, color: '#9999A5', fontSize: 13 },
});
