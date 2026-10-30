import {
  loadPersonalEvents,
  savePersonalEvent,
} from '../services/personalEvents';
import AddEventScreen, { type PersonalEvent } from './AddEventScreen';
import { useEffect, useState } from 'react';

import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { Feather } from '@expo/vector-icons';

import { createApi } from '../services/api';
import type { CampusEvent } from '../data/events';

const api = createApi('http://127.0.0.1:8000', () => undefined);

type CalendarEvent = CampusEvent & {
  end_at?: string | null;
  status?: 'ACTIVE' | 'CANCELLED' | 'HIDDEN';
};

function isSameDay(a: Date, b: Date) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function getEventDate(event: CalendarEvent) {
  const date = new Date(event.start_at);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatEventTime(event: CalendarEvent) {
  if (event.is_all_day) return 'All day';

  const start = getEventDate(event);
  if (!start) return 'Time TBA';

  const formatter = new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });

  const end = event.end_at ? new Date(event.end_at) : null;

  return end && !Number.isNaN(end.getTime())
    ? `${formatter.format(start)}–${formatter.format(end)}`
    : formatter.format(start);
}
const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

function formatMonth(date: Date) {
  return date.toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  });
}

function formatSelectedDate(date: Date) {
  return date.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
}

export default function CalendarScreen() {
  const [selectedDate, setSelectedDate] = useState(new Date());

  const [visibleMonth, setVisibleMonth] = useState(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1)
  );

  const [activeTab, setActiveTab] = useState<'My Calendar' | 'Friends'>(
    'My Calendar'
  );

  const [showAddEvent, setShowAddEvent] = useState(false);
  const [personalEvents, setPersonalEvents] = useState<PersonalEvent[]>([]);
  function hasPersonalEvent(day: number) {
  const date = new Date(year, month, day);

  return personalEvents.some((event) =>
    isSameDay(new Date(event.start_at), date)
  );
}
  useEffect(() => {
  let mounted = true;

  async function loadSavedEvents() {
    try {
      const saved = await loadPersonalEvents();

      if (mounted) {
        setPersonalEvents(saved);
      }
    } catch (error) {
      console.error('Failed to load personal events:', error);
    }
  }

  void loadSavedEvents();

  return () => {
    mounted = false;
  };
}, []);

  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const year = visibleMonth.getFullYear();
  const month = visibleMonth.getMonth();

  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const calendarDays: (number | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  useEffect(() => {
  const controller = new AbortController();

  async function fetchMonthEvents() {
    setLoading(true);
    setError(null);
    setEvents([]);

    try {
      const start = new Date(year, month, 1);
      const end = new Date(year, month + 1, 1);

      const allEvents: CalendarEvent[] = [];
      const seenCursors = new Set<string>();

      let cursor: string | undefined;
      let finished = false;

      for (let pageNumber = 0; pageNumber < 50; pageNumber++) {
        const page = await api.events(
          start,
          end,
          cursor,
          controller.signal
        );

        allEvents.push(...(page.items as CalendarEvent[]));

        if (!page.next_cursor) {
          finished = true;
          break;
        }

        if (seenCursors.has(page.next_cursor)) {
          throw new Error('Event pagination did not advance.');
        }

        seenCursors.add(page.next_cursor);
        cursor = page.next_cursor;
      }

      if (!finished) {
        throw new Error('Too many event pages to load.');
      }

      if (!controller.signal.aborted) {
        const unique = new Map(
          allEvents.map(event => [event.id, event])
        );

        setEvents(
          [...unique.values()].filter(
            event => event.status !== 'HIDDEN'
          )
        );
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to load events.'
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }

  void fetchMonthEvents();

  return () => controller.abort();
}, [year, month]);

const selectedEvents = events
  .filter(event => {
    const date = getEventDate(event);
    return date !== null && isSameDay(date, selectedDate);
  })
  .sort(
    (a, b) =>
      new Date(a.start_at).getTime() -
      new Date(b.start_at).getTime()
  );

  const selectedPersonalEvents = personalEvents
  .filter((event) => {
    const date = new Date(event.start_at);
    return isSameDay(date, selectedDate);
  })
  .sort(
    (a, b) =>
      new Date(a.start_at).getTime() -
      new Date(b.start_at).getTime()
  );

  function changeMonth(offset: number) {
    const nextMonth = new Date(year, month + offset, 1);
    setVisibleMonth(nextMonth);
    setSelectedDate(nextMonth);
  }

  function selectDay(day: number) {
    setSelectedDate(new Date(year, month, day));
  }

  if (showAddEvent) {
  return (
    <AddEventScreen
      selectedDate={selectedDate}
      onCancel={() => setShowAddEvent(false)}
      onSave={async (event) => {
        try {
          const updatedEvents = await savePersonalEvent(event);

          setPersonalEvents(updatedEvents);
          setSelectedDate(new Date(event.start_at));
          setVisibleMonth(
            new Date(
              new Date(event.start_at).getFullYear(),
              new Date(event.start_at).getMonth(),
              1
            )
          );
          setShowAddEvent(false);
        } catch (error) {
          console.error('Failed to save event:', error);
          Alert.alert('Save failed', 'Could not save your event. Please try again.');
        }
      }}
    />
  );
}

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      <Text style={styles.headerDate}>
        {new Date().toLocaleDateString('en-US', {
          weekday: 'long',
          month: 'long',
          day: 'numeric',
        })}
      </Text>

      <View style={styles.titleRow}>
  <Text style={styles.title}>Calendar</Text>

  <Pressable
    style={styles.addButton}
    onPress={() => setShowAddEvent(true)}
  >
    <Feather name="plus" size={16} color="#FFFFFF" />
    <Text style={styles.addButtonText}>Add Event</Text>
  </Pressable>
</View>

      <View style={styles.tabs}>
        {(['My Calendar', 'Friends'] as const).map(tab => (
          <Pressable
            key={tab}
            onPress={() => setActiveTab(tab)}
            style={[
              styles.tab,
              activeTab === tab && styles.activeTab,
            ]}
          >
            <Text
              style={[
                styles.tabText,
                activeTab === tab && styles.activeTabText,
              ]}
            >
              {tab}
            </Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.monthHeader}>
        <Pressable
          onPress={() => changeMonth(-1)}
          style={styles.arrowButton}
        >
          <Feather name="chevron-left" size={20} color="#444" />
        </Pressable>

        <Text style={styles.monthTitle}>{formatMonth(visibleMonth)}</Text>

        <Pressable
          onPress={() => changeMonth(1)}
          style={styles.arrowButton}
        >
          <Feather name="chevron-right" size={20} color="#444" />
        </Pressable>
      </View>

      <View style={styles.calendarGrid}>
        {WEEKDAYS.map((day, index) => (
          <View key={index} style={styles.dayCell}>
            <Text style={styles.weekday}>{day}</Text>
          </View>
        ))}

        {calendarDays.map((day, index) => {
          if (day === null) {
            return <View key={`empty-${index}`} style={styles.dayCell} />;
          }

          const selected =
            selectedDate.getFullYear() === year &&
            selectedDate.getMonth() === month &&
            selectedDate.getDate() === day;

          return (
            <Pressable
              key={`${year}-${month}-${day}`}
              onPress={() => selectDay(day)}
              style={styles.dayCell}
            >
              <View
                style={[
                  styles.dateCircle,
                  selected && styles.selectedCircle,
                ]}
              >
                <Text
                  style={[
                    styles.dayText,
                    selected && styles.selectedDayText,
                  ]}
                >
                  {day}
                </Text>
                {(events.some(event => {
                  const date = getEventDate(event);
                  return date !== null &&
                    isSameDay(date, new Date(year, month, day));
                }) || hasPersonalEvent(day)) && (
                  <View style={[
                    styles.eventDot,
                    selected && styles.selectedEventDot,
                  ]} />
                )}
              </View>
            </Pressable>
          );
        })}
      </View>

      <View style={styles.scheduleSection}>
        <Text style={styles.sectionLabel}>
          {activeTab === 'My Calendar' ? 'YOUR SCHEDULE' : 'PLAN TOGETHER'}
        </Text>

        <Text style={styles.selectedDateTitle}>
          {activeTab === 'My Calendar'
            ? formatSelectedDate(selectedDate)
            : "Friends' Schedules"}
        </Text>

        {activeTab === 'Friends' ? (
          <Text style={styles.emptyMessage}>
            Friends calendar integration coming soon.
          </Text>
        ) : (
          <View style={styles.eventList}>
            {selectedPersonalEvents.length > 0 && (
              <>
                <Text style={styles.eventCount}>MY EVENTS</Text>
                {selectedPersonalEvents.map(event => (
                  <View key={event.id} style={styles.eventCard}>
                    <Text style={styles.eventCardTime}>
                      {event.is_all_day
                        ? 'All day'
                        : new Date(event.start_at).toLocaleTimeString(
                            'en-US',
                            {hour: 'numeric', minute: '2-digit'}
                          )}
                    </Text>
                    <Text style={styles.eventCardTitle}>
                      {event.title}
                    </Text>
                    <Text style={styles.eventCardLocation}>
                      {event.location || 'No location'}
                    </Text>
                  </View>
                ))}
              </>
            )}

            {loading ? (
              <ActivityIndicator color="#57068C" />
            ) : error ? (
              <Text style={styles.emptyMessage}>
                Unable to load NYU events: {error}
              </Text>
            ) : selectedEvents.length > 0 ? (
              <>
                <Text style={styles.eventCount}>NYU EVENTS</Text>
                {selectedEvents.map(event => (
                  <View key={event.id} style={styles.eventCard}>
                    <Text style={styles.eventCardTime}>
                      {formatEventTime(event)}
                    </Text>
                    <Text style={styles.eventCardTitle}>
                      {event.title}
                    </Text>
                    <Text style={styles.eventCardLocation}>
                      {event.location_name || 'Location TBA'}
                    </Text>
                  </View>
                ))}
              </>
            ) : selectedPersonalEvents.length === 0 ? (
              <Text style={styles.emptyMessage}>
                No events scheduled for this date.
              </Text>
            ) : null}
          </View>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  titleRow: {
  flexDirection: 'row',
  alignItems: 'center',
  justifyContent: 'space-between',
},
addButton: {
  backgroundColor: '#171717',
  borderRadius: 10,
  paddingHorizontal: 12,
  paddingVertical: 10,
  flexDirection: 'row',
  alignItems: 'center',
  gap: 5,
},
addButtonText: {
  color: '#FFFFFF',
  fontSize: 12,
  fontWeight: '600',
},  
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 24,
    paddingBottom: 40,
  },
  headerDate: {
    color: '#92929D',
    fontSize: 14,
  },
  title: {
    fontSize: 29,
    fontWeight: '700',
    marginTop: 10,
    color: '#171717',
  },
  tabs: {
    flexDirection: 'row',
    marginTop: 42,
    borderBottomWidth: 1,
    borderBottomColor: '#EEEEEE',
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 14,
  },
  activeTab: {
    borderBottomWidth: 2,
    borderBottomColor: '#171717',
  },
  tabText: {
    fontSize: 13,
    color: '#999999',
  },
  activeTabText: {
    color: '#171717',
    fontWeight: '600',
  },
  monthHeader: {
    marginTop: 26,
    marginBottom: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  arrowButton: {
    width: 36,
    height: 36,
    borderWidth: 1,
    borderColor: '#EAEAEA',
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  monthTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#171717',
  },
  calendarGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  dayCell: {
    width: '14.2857%',
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
  },
  weekday: {
    fontSize: 11,
    color: '#A0A0A8',
  },
  dateCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    justifyContent: 'center',
    alignItems: 'center',
  },
  selectedCircle: {
    backgroundColor: '#1C1C1E',
  },
  dayText: {
    fontSize: 13,
    color: '#292929',
  },
  selectedDayText: {
    color: '#FFFFFF',
  },
  scheduleSection: {
    marginTop: 40,
    paddingTop: 28,
    borderTopWidth: 1,
    borderTopColor: '#EEEEEE',
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#9999A3',
    letterSpacing: 1.4,
  },
  selectedDateTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#1C1C1E',
    marginTop: 10,
  },
  emptyMessage: {
    marginTop: 24,
    color: '#9999A3',
    fontSize: 14,
  },
  eventDot: {
  width: 4,
  height: 4,
  borderRadius: 2,
  backgroundColor: '#1C1C1E',
  position: 'absolute',
  bottom: 5,
},
selectedEventDot: {
  backgroundColor: '#FFFFFF',
},
eventList: {
  marginTop: 20,
},
eventCount: {
  fontSize: 12,
  color: '#9999A3',
  marginBottom: 12,
},
eventCard: {
  paddingVertical: 18,
  paddingHorizontal: 10,
  borderLeftWidth: 3,
  borderLeftColor: '#EAEAEA',
  borderBottomWidth: 1,
  borderBottomColor: '#EEEEEE',
  marginBottom: 12,
},
eventCardTime: {
  fontSize: 12,
  color: '#8F8F98',
  marginBottom: 8,
},
eventCardTitle: {
  fontSize: 15,
  fontWeight: '600',
  color: '#171717',
},
eventCardLocation: {
  fontSize: 12,
  color: '#9C9CA6',
  marginTop: 6,
},
});