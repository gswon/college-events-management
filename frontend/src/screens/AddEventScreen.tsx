
import { useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';

export type PersonalEvent = {
  id: string;
  title: string;
  start_at: string;
  end_at: string;
  is_all_day: boolean;
  location: string;
  notes: string;
};

type Props = {
  selectedDate: Date;
  onCancel: () => void;
  onSave: (event: PersonalEvent) => void;
};

function dateText(date: Date) {
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export default function AddEventScreen({
  selectedDate,
  onCancel,
  onSave,
}: Props) {
  const [title, setTitle] = useState('');
  const [date, setDate] = useState(new Date(selectedDate));
  const [allDay, setAllDay] = useState(false);
  const [startTime, setStartTime] = useState('14:00');
  const [endTime, setEndTime] = useState('15:00');
  const [location, setLocation] = useState('');
  const [notes, setNotes] = useState('');

  function changeDate(offset: number) {
    setDate(previous =>
      new Date(
        previous.getFullYear(),
        previous.getMonth(),
        previous.getDate() + offset
      )
    );
  }

  function saveEvent() {
    if (!title.trim()) {
      Alert.alert('Missing title', 'Please enter an event title.');
      return;
    }

    const timePattern = /^([01]\d|2[0-3]):[0-5]\d$/;

    if (!allDay && (
      !timePattern.test(startTime) ||
      !timePattern.test(endTime)
    )) {
      Alert.alert('Invalid time', 'Use HH:MM format, such as 14:00.');
      return;
    }

    const [startHour, startMinute] = startTime.split(':').map(Number);
    const [endHour, endMinute] = endTime.split(':').map(Number);

    const start = new Date(
      date.getFullYear(),
      date.getMonth(),
      date.getDate(),
      allDay ? 0 : startHour,
      allDay ? 0 : startMinute
    );

    const end = allDay
      ? new Date(date.getFullYear(), date.getMonth(), date.getDate() + 1)
      : new Date(
          date.getFullYear(),
          date.getMonth(),
          date.getDate(),
          endHour,
          endMinute
        );

    if (end <= start) {
      Alert.alert('Invalid time', 'End time must be after start time.');
      return;
    }

    onSave({
      id: `personal-${Date.now()}`,
      title: title.trim(),
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      is_all_day: allDay,
      location: location.trim(),
      notes: notes.trim(),
    });
  }

  return (
    <View style={styles.screen}>
      <View style={styles.header}>
        <Pressable onPress={onCancel}>
          <Text style={styles.cancel}>Cancel</Text>
        </Pressable>
        <Text style={styles.headerTitle}>Add Event</Text>
        <View style={{ width: 48 }} />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.label}>Event title</Text>
        <TextInput
          style={styles.input}
          value={title}
          onChangeText={setTitle}
          placeholder="e.g. Study group"
          placeholderTextColor="#A0A0A8"
        />

        <Text style={styles.sectionLabel}>WHEN</Text>

        <View style={styles.dateRow}>
          <Feather name="calendar" size={18} color="#92929D" />
          <Text style={styles.dateLabel}>Date</Text>
          <View style={styles.dateControls}>
            <Pressable onPress={() => changeDate(-1)} style={styles.dateArrow}>
              <Feather name="chevron-left" size={18} color="#171717" />
            </Pressable>
            <Text style={styles.dateValue}>{dateText(date)}</Text>
            <Pressable onPress={() => changeDate(1)} style={styles.dateArrow}>
              <Feather name="chevron-right" size={18} color="#171717" />
            </Pressable>
          </View>
        </View>

        <View style={styles.allDayRow}>
          <Text style={styles.dateLabel}>All-day</Text>
          <Switch
            value={allDay}
            onValueChange={setAllDay}
            trackColor={{ false: '#E7E7EB', true: '#171717' }}
          />
        </View>

        {!allDay && (
          <View style={styles.timeRow}>
            <View style={styles.timeBox}>
              <Text style={styles.timeLabel}>Start time (HH:MM)</Text>
              <TextInput
                style={styles.timeInput}
                value={startTime}
                onChangeText={setStartTime}
                placeholder="14:00"
                keyboardType="numbers-and-punctuation"
              />
            </View>
            <View style={styles.timeBox}>
              <Text style={styles.timeLabel}>End time (HH:MM)</Text>
              <TextInput
                style={styles.timeInput}
                value={endTime}
                onChangeText={setEndTime}
                placeholder="15:00"
                keyboardType="numbers-and-punctuation"
              />
            </View>
          </View>
        )}

        <Text style={styles.label}>Location (optional)</Text>
        <TextInput
          style={styles.input}
          value={location}
          onChangeText={setLocation}
          placeholder="e.g. Bobst Library, Room 402"
          placeholderTextColor="#A0A0A8"
        />

        <Text style={styles.label}>Notes (optional)</Text>
        <TextInput
          style={[styles.input, styles.notesInput]}
          value={notes}
          onChangeText={setNotes}
          placeholder="Add notes..."
          multiline
          textAlignVertical="top"
          placeholderTextColor="#A0A0A8"
        />
      </ScrollView>

      <View style={styles.footer}>
        <Text style={styles.privacy}>Only you · Saves to My Calendar</Text>
        <Pressable style={styles.saveButton} onPress={saveEvent}>
          <Text style={styles.saveText}>Save Event</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#FFFFFF' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 20,
  },
  cancel: { color: '#66666C', fontSize: 14 },
  headerTitle: { color: '#171717', fontSize: 17, fontWeight: '700' },
  scroll: { flex: 1 },
  content: { paddingHorizontal: 20, paddingBottom: 30 },
  label: { fontSize: 13, color: '#55555C', marginTop: 22, marginBottom: 8 },
  input: {
    borderWidth: 1,
    borderColor: '#E8E8ED',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 13,
    fontSize: 15,
    color: '#171717',
  },
  sectionLabel: {
    color: '#9999A3',
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 1.2,
    marginTop: 30,
    marginBottom: 12,
  },
  dateRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#EEEEF0',
  },
  dateLabel: { fontSize: 14, color: '#171717' },
  dateControls: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end' },
  dateArrow: { padding: 4 },
  dateValue: { fontSize: 12, color: '#171717', marginHorizontal: 2 },
  allDayRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 16,
  },
  timeRow: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  timeBox: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#E8E8ED',
    borderRadius: 12,
    padding: 12,
  },
  timeLabel: { color: '#9999A3', fontSize: 11 },
  timeInput: { color: '#171717', fontSize: 20, fontWeight: '600', marginTop: 6, padding: 0 },
  notesInput: { minHeight: 100 },
  footer: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 12 },
  privacy: { color: '#A0A0A8', textAlign: 'center', fontSize: 12, marginBottom: 12 },
  saveButton: {
    backgroundColor: '#171717',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
  },
  saveText: { color: '#FFFFFF', fontWeight: '600', fontSize: 15 },
});
