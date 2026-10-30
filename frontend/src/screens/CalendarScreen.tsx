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
import { calendarFriendsApi } from '../services/calendarFriendsApi';
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
  const [editingEvent, setEditingEvent] = useState<PersonalEvent | null>(null);
  const [personalEvents, setPersonalEvents] = useState<PersonalEvent[]>([]);
  const [overlayFriends, setOverlayFriends] = useState<
    { id: number; name: string }[]
  >([]);
  const [selectedFriendIds, setSelectedFriendIds] = useState<number[]>([]);
  const [overlayItems, setOverlayItems] = useState<
    { userId: number; name: string; item: import('../services/calendarFriendsApi').CalendarItem }[]
  >([]);
  const [overlayLoading, setOverlayLoading] = useState(false);
  const [overlayError, setOverlayError] = useState<string | null>(null);

  const [backendEvents, setBackendEvents] = useState<PersonalEvent[]>([]);
  const allPersonalEvents = [...personalEvents, ...backendEvents];
  function hasPersonalEvent(day: number) {
  const date = new Date(year, month, day);

  return allPersonalEvents.some((event) =>
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

  // Load personal events saved in the local test Backend (port 8001).
  useEffect(() => {
    let active = true;

    async function loadBackendEvents() {
      try {
        const start = new Date(year, month, 1).toISOString();
        const end = new Date(year, month + 1, 1).toISOString();

        const items = await calendarFriendsApi.getMyCalendar(start, end);

        const mapped: PersonalEvent[] = items
          .filter(
            (item) =>
              item.type === 'PERSONAL' &&
              item.id !== undefined &&
              typeof item.title === 'string'
          )
          .map((item) => ({
            id: `backend-${item.id}`,
            title: item.title!,
            start_at: item.start_at,
            end_at: item.end_at,
            is_all_day: item.is_all_day ?? false,
            location: item.location ?? '',
            notes: '',
          }));

        if (active) {
          setBackendEvents(mapped);
        }
      } catch (error) {
        console.error('Failed to load Backend calendar:', error);
        if (active) {
          setBackendEvents([]);
        }
      }
    }

    setBackendEvents([]);
    void loadBackendEvents();

    return () => {
      active = false;
    };
  }, [year, month]);


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

  useEffect(() => {
    if (activeTab !== 'Friends') return;

    let active = true;

    calendarFriendsApi.getFriends()
      .then((friends) => {
        if (!active) return;

        const available = friends.map((friend) => ({
          id: friend.user.id,
          name: friend.user.display_name,
        }));

        setOverlayFriends(available);
        setSelectedFriendIds((previous) =>
          previous.filter((id) =>
            available.some((friend) => friend.id === id)
          )
        );
      })
      .catch((err) => {
        if (active) {
          setOverlayError(
            err instanceof Error ? err.message : 'Could not load friends.'
          );
        }
      });

    return () => { active = false; };
  }, [activeTab]);

  useEffect(() => {
    if (activeTab !== 'Friends' || selectedFriendIds.length === 0) {
      setOverlayItems([]);
      setOverlayLoading(false);
      return;
    }

    let active = true;
    setOverlayLoading(true);
    setOverlayError(null);

    const start = new Date(year, month, 1).toISOString();
    const end = new Date(year, month + 1, 1).toISOString();

    calendarFriendsApi
      .getCalendarOverlay(selectedFriendIds, start, end)
      .then((calendars) => {
        if (!active) return;

        const selected = new Set(selectedFriendIds);
        const combined = calendars
          .filter((calendar) => selected.has(calendar.user_id))
          .flatMap((calendar) => {
            const friend = overlayFriends.find(
              (item) => item.id === calendar.user_id
            );

            return calendar.items.map((item) => ({
              userId: calendar.user_id,
              name: friend?.name ?? `User ${calendar.user_id}`,
              item,
            }));
          });

        setOverlayItems(combined);
      })
      .catch((err) => {
        if (active) {
          setOverlayError(
            err instanceof Error ? err.message : 'Could not load schedules.'
          );
          setOverlayItems([]);
        }
      })
      .finally(() => {
        if (active) setOverlayLoading(false);
      });

    return () => { active = false; };
  }, [activeTab, year, month, selectedFriendIds, overlayFriends]);

  const selectedOverlayItems = overlayItems
    .filter(({ item }) => {
      const start = new Date(item.start_at);
      const end = new Date(item.end_at);
      return start <= selectedDate && end > selectedDate ||
        isSameDay(start, selectedDate);
    })
    .sort(
      (a, b) =>
        new Date(a.item.start_at).getTime() -
        new Date(b.item.start_at).getTime()
    );

  const selectedPersonalEvents = allPersonalEvents
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


  function openPersonalEventActions(event: PersonalEvent) {
    if (!event.id.startsWith('backend-')) {
      Alert.alert(
        'Local Event',
        'This event was saved before Backend integration. It has not been migrated.'
      );
      return;
    }

    const entryId = Number(event.id.slice('backend-'.length));

    if (!Number.isSafeInteger(entryId) || entryId <= 0) {
      Alert.alert('Error', 'Invalid Backend event ID.');
      return;
    }

    Alert.alert(
      event.title,
      'What would you like to do?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Edit',
          onPress: async () => {
            try {
              const detail = await calendarFriendsApi.getPersonalEntry(entryId);

              setEditingEvent({
                id: event.id,
                title: detail.title,
                start_at: detail.start_at,
                end_at: detail.end_at,
                is_all_day: detail.is_all_day ?? false,
                location: detail.location ?? '',
                notes: detail.description ?? '',
              });
            } catch (error) {
              Alert.alert(
                'Could not open event',
                error instanceof Error
                  ? error.message
                  : 'Failed to load event details.'
              );
            }
          },
        },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => {
            Alert.alert(
              'Delete Event?',
              'This event will be permanently deleted.',
              [
                { text: 'Cancel', style: 'cancel' },
                {
                  text: 'Delete',
                  style: 'destructive',
                  onPress: async () => {
                    try {
                      await calendarFriendsApi.deletePersonalEntry(entryId);

                      setBackendEvents((current) =>
                        current.filter((item) => item.id !== event.id)
                      );
                    } catch (error) {
                      Alert.alert(
                        'Delete failed',
                        error instanceof Error
                          ? error.message
                          : 'Could not delete the event.'
                      );
                    }
                  },
                },
              ]
            );
          },
        },
      ]
    );
  }

  if (editingEvent) {
    return (
      <AddEventScreen
        key={editingEvent.id}
        selectedDate={new Date(editingEvent.start_at)}
        initialEvent={editingEvent}
        onCancel={() => setEditingEvent(null)}
        onSave={async (updatedEvent) => {
          const entryId = Number(
            editingEvent.id.slice('backend-'.length)
          );

          try {
            const updated = await calendarFriendsApi.updatePersonalEntry(
              entryId,
              {
                title: updatedEvent.title,
                description: updatedEvent.notes,
                location: updatedEvent.location,
                start_at: updatedEvent.start_at,
                end_at: updatedEvent.end_at,
                is_all_day: updatedEvent.is_all_day,
              }
            );

            setBackendEvents((current) =>
              current.map((item) =>
                item.id === editingEvent.id
                  ? {
                      ...updatedEvent,
                      id: editingEvent.id,
                      start_at: updated.start_at,
                      end_at: updated.end_at,
                    }
                  : item
              )
            );

            const nextDate = new Date(updated.start_at);

            setSelectedDate(nextDate);
            setVisibleMonth(
              new Date(nextDate.getFullYear(), nextDate.getMonth(), 1)
            );
            setEditingEvent(null);
          } catch (error) {
            Alert.alert(
              'Update failed',
              error instanceof Error
                ? error.message
                : 'Could not save changes.'
            );
          }
        }}
      />
    );
  }

  if (showAddEvent) {
  return (
    <AddEventScreen
      selectedDate={selectedDate}
      onCancel={() => setShowAddEvent(false)}
      onSave={async (event) => {
        try {
          const created = await calendarFriendsApi.createPersonalEntry({
            title: event.title,
            description: event.notes || null,
            location: event.location || null,
            start_at: event.start_at,
            end_at: event.end_at,
            is_all_day: event.is_all_day,
          });

          setBackendEvents((current) => [
            ...current,
            {
              ...event,
              id: `backend-${created.id}`,
            },
          ]);
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
          <View style={styles.eventList}>
            <Text style={styles.eventCount}>SELECT FRIENDS</Text>

            {overlayFriends.length === 0 ? (
              <Text style={styles.emptyMessage}>No friends added yet.</Text>
            ) : (
              overlayFriends.map((friend) => {
                const selected = selectedFriendIds.includes(friend.id);

                return (
                  <Pressable
                    key={friend.id}
                    style={{
                      flexDirection: 'row',
                      alignItems: 'center',
                      paddingVertical: 12,
                      gap: 12,
                    }}
                    onPress={() => {
                      setSelectedFriendIds((previous) =>
                        selected
                          ? previous.filter((id) => id !== friend.id)
                          : previous.length < 10
                            ? [...previous, friend.id]
                            : previous
                      );
                    }}
                  >
                    <Feather
                      name={selected ? 'check-square' : 'square'}
                      size={22}
                      color={selected ? '#57068C' : '#999999'}
                    />
                    <Text style={styles.eventCardTitle}>{friend.name}</Text>
                  </Pressable>
                );
              })
            )}

            {overlayLoading ? (
              <ActivityIndicator color="#57068C" />
            ) : overlayError ? (
              <Text style={styles.emptyMessage}>{overlayError}</Text>
            ) : selectedFriendIds.length === 0 ? (
              <Text style={styles.emptyMessage}>
                Select friends to view shared schedules.
              </Text>
            ) : selectedOverlayItems.length === 0 ? (
              <Text style={styles.emptyMessage}>
                No shared events for this date.
              </Text>
            ) : (
              <>
                <Text style={styles.eventCount}>SHARED SCHEDULES</Text>
                {selectedOverlayItems.map(({ userId, name, item }, index) => (
                  <View
                    key={`${userId}-${item.type}-${item.id ?? index}`}
                    style={styles.eventCard}
                  >
                    <Text style={styles.eventCardTime}>
                      {item.is_all_day
                        ? 'All day'
                        : new Date(item.start_at).toLocaleTimeString(
                            'en-US',
                            { hour: 'numeric', minute: '2-digit' }
                          )}
                    </Text>
                    <Text style={styles.eventCardTitle}>
                      {item.type === 'BUSY' ? 'Busy' : item.title ?? 'Event'}
                    </Text>
                    <Text style={styles.eventCardLocation}>{name}</Text>
                    {item.type !== 'BUSY' && item.location ? (
                      <Text style={styles.eventCardLocation}>
                        {item.location}
                      </Text>
                    ) : null}
                  </View>
                ))}
              </>
            )}
          </View>
        ) : (
          <View style={styles.eventList}>
            {selectedPersonalEvents.length > 0 && (
              <>
                <Text style={styles.eventCount}>MY EVENTS</Text>
                {selectedPersonalEvents.map(event => (
                  <Pressable
                    key={event.id}
                    style={styles.eventCard}
                    onPress={() => openPersonalEventActions(event)}
                  >
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
                  </Pressable>
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