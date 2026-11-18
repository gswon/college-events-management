
import { useState } from 'react';
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import DateTimePicker from '@react-native-community/datetimepicker';

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
  initialEvent?: PersonalEvent;
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
  initialEvent,
  onCancel,
  onSave,
}: Props) {
  const initialStart = initialEvent
    ? new Date(initialEvent.start_at)
    : selectedDate;
  const initialEnd = initialEvent
    ? new Date(initialEvent.end_at)
    : null;

  function hhmm(date: Date) {
    return String(date.getHours()).padStart(2, '0')
      + ':'
      + String(date.getMinutes()).padStart(2, '0');
  }

  const [title, setTitle] = useState(initialEvent?.title ?? '');
  const [date, setDate] = useState(new Date(initialStart));
  const [allDay, setAllDay] = useState(initialEvent?.is_all_day ?? false);
  const [startTime, setStartTime] = useState(
    initialEvent ? hhmm(initialStart) : '14:00'
  );
  const [endTime, setEndTime] = useState(
    initialEnd ? hhmm(initialEnd) : '15:00'
  );
  const [location, setLocation] = useState(initialEvent?.location ?? '');
  const [notes, setNotes] = useState(initialEvent?.notes ?? '');
  const [activeTimePicker, setActiveTimePicker] = useState<'start' | 'end' | null>(null);
  const [datePickerOpen, setDatePickerOpen] = useState(false);
  const [datePickerMonth, setDatePickerMonth] = useState(new Date(date.getFullYear(), date.getMonth(), 1));
  const [draftTime, setDraftTime] = useState(new Date());
  const [timeSelection, setTimeSelection] = useState<'start' | 'end'>('start');

  function openTimePicker(which: 'start' | 'end') {
    const [hour, minute] = (which === 'start' ? startTime : endTime).split(':').map(Number);
    const value = new Date(date);
    value.setHours(hour, minute, 0, 0);
    setDraftTime(value);
    setTimeSelection(which);
    setActiveTimePicker(which);
  }

  function applyTime() {
    const time = hhmm(draftTime);
    if (timeSelection === 'start') setStartTime(time);
    else setEndTime(time);
    setActiveTimePicker(null);
  }
  function formatTime(value: string) {
    const [h, m] = value.split(':').map(Number);
    const period = h < 12 ? 'AM' : 'PM';
    return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${period}`;
  }
  const dateCount = new Date(datePickerMonth.getFullYear(), datePickerMonth.getMonth()+1,0).getDate();
  const dayOffset = new Date(datePickerMonth.getFullYear(), datePickerMonth.getMonth(),1).getDay();
  const displayPickerDays = Array.from({length:Math.ceil((dayOffset+dateCount)/7)*7}, (_,i)=> i-dayOffset+1);
  const startMinute = Number(startTime.split(':')[0])*60+Number(startTime.split(':')[1]);
  const endMinute = Number(endTime.split(':')[0])*60+Number(endTime.split(':')[1]);
  const interval = endMinute - startMinute;


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
      id: initialEvent?.id ?? `personal-${Date.now()}`,
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
        <Text style={styles.headerTitle}>
          {initialEvent ? 'Edit Event' : 'Add Event'}
        </Text>
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
          <Pressable
            style={styles.dateControls}
            onPress={() => {
              setDatePickerMonth(new Date(date.getFullYear(), date.getMonth(), 1));
              setDatePickerOpen(true);
            }}
            accessibilityRole="button"
            accessibilityLabel="Choose event date"
          >
            <Text style={styles.dateValue}>{dateText(date)}</Text>
            <Feather name="chevron-right" size={16} color="#92929D" />
          </Pressable>
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
              <Pressable
                onPress={() => openTimePicker('start')}
                accessibilityLabel="Select start time"
              >
                <Text style={styles.timeInput}>
                  {formatTime(startTime)}
                </Text>
              </Pressable>
            </View>
            <View style={styles.timeBox}>
              <Text style={styles.timeLabel}>End time (HH:MM)</Text>
              <Pressable
                onPress={() => openTimePicker('end')}
                accessibilityLabel="Select end time"
              >
                <Text style={styles.timeInput}>
                  {formatTime(endTime)}
                </Text>
              </Pressable>
            </View>
          </View>
        )}

        {!allDay && (
          <View style={styles.timeHelper}>
            <Text style={styles.timeHelperText}>Tap a time to change it</Text>
            <Text style={styles.timeHelperText}>
              {interval > 0 ? `${Math.floor(interval / 60)}h${interval % 60 ? ` ${interval % 60}m` : ''}` : 'Check time'} · Local time
            </Text>
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

      <Modal visible={datePickerOpen} transparent animationType="fade" onRequestClose={() => setDatePickerOpen(false)}>
        <View style={styles.modalBackdrop}>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setDatePickerOpen(false)} />
          <View style={styles.dateModal}>
            <View style={styles.modalTopRow}>
              <Text style={styles.modalTitle}>Select date</Text>
              <Pressable onPress={() => setDatePickerOpen(false)}><Text style={styles.cancel}>Cancel</Text></Pressable>
            </View>
            <View style={styles.dateMonthRow}>
              <Pressable onPress={() => setDatePickerMonth(new Date(datePickerMonth.getFullYear(), datePickerMonth.getMonth()-1, 1))} accessibilityLabel="Previous month">
                <Feather name="chevron-left" size={18} color="#777" />
              </Pressable>
              <Text style={styles.dateMonthTitle}>{datePickerMonth.toLocaleDateString('en-US',{month:'long',year:'numeric'})}</Text>
              <Pressable onPress={() => setDatePickerMonth(new Date(datePickerMonth.getFullYear(), datePickerMonth.getMonth()+1, 1))} accessibilityLabel="Next month">
                <Feather name="chevron-right" size={18} color="#777" />
              </Pressable>
            </View>
            <View style={styles.dateGrid}>
              {['S','M','T','W','T','F','S'].map((name,index)=>(
                <View key={`weekday-${index}`} style={styles.dateCell}><Text style={styles.weekday}>{name}</Text></View>
              ))}
              {displayPickerDays.map((day,index)=>(
                <Pressable
                  key={`date-${index}`}
                  style={styles.dateCell}
                  disabled={day < 1 || day > dateCount}
                  onPress={() => {setDate(new Date(datePickerMonth.getFullYear(),datePickerMonth.getMonth(),day));setDatePickerOpen(false);}}
                >
                  {day >= 1 && day <= dateCount ? (
                    <View style={[styles.dateNumberCircle,
                      date.getDate()===day && date.getMonth()===datePickerMonth.getMonth() && date.getFullYear()===datePickerMonth.getFullYear() && styles.selectedDateNumber]}>
                      <Text style={[styles.dateNumber,
                        date.getDate()===day && date.getMonth()===datePickerMonth.getMonth() && date.getFullYear()===datePickerMonth.getFullYear() && styles.selectedDateNumberText]}>{day}</Text>
                    </View>
                  ) : null}
                </Pressable>
              ))}
            </View>
            <Text style={styles.modalHint}>Choose a date to apply</Text>
          </View>
        </View>
      </Modal>

      <Modal visible={activeTimePicker !== null} transparent animationType="slide" onRequestClose={() => setActiveTimePicker(null)}>
        <View style={styles.timeBackdrop}>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setActiveTimePicker(null)} />
          <View style={styles.timeSheet}>
            <View style={styles.sheetHandle}/>
            <View style={styles.modalTopRow}>
              <Text style={styles.sheetTitle}>Set time</Text>
              <Pressable onPress={() => setActiveTimePicker(null)} accessibilityLabel="Close time picker"><Feather name="x" size={22} color="#555" /></Pressable>
            </View>
            <Text style={styles.sheetDate}>{date.toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'})}</Text>
            <View style={styles.timeRow}>
              {(['start','end'] as const).map(which => (
                <Pressable
                  key={which}
                  style={[styles.timeBox, timeSelection === which && styles.activeTimeBox]}
                  onPress={() => openTimePicker(which)}
                >
                  <Text style={[styles.timeLabel, timeSelection === which && styles.activeTimeText]}>{which === 'start' ? 'Start' : 'End'}</Text>
                  <Text style={[styles.timeInput, timeSelection === which && styles.activeTimeText]}>{formatTime(which === 'start' ? startTime : endTime)}</Text>
                </Pressable>
              ))}
            </View>
            <Text style={styles.timeWheelHint}>Scroll to set the {timeSelection} time</Text>
            <DateTimePicker
              value={draftTime}
              mode="time"
              display="spinner"
              minuteInterval={5}
              onValueChange={(_, value) => {if(value) setDraftTime(value);}}
              style={styles.nativeTimePicker}
            />
            <Text style={styles.timeSummary}>{formatTime(startTime)}–{formatTime(endTime)}</Text>
            <Pressable style={styles.saveButton} onPress={applyTime}><Text style={styles.saveText}>Set Time</Text></Pressable>
          </View>
        </View>
      </Modal>

      <View style={styles.footer}>
        <View style={styles.privacyRow}>
          <Feather name="lock" size={12} color="#9999A3" />
          <Text style={styles.privacy}>Only you · Saves to My Calendar</Text>
        </View>
        <Pressable style={styles.saveButton} onPress={saveEvent}>
          <Text style={styles.saveText}>
            {initialEvent ? 'Save Changes' : 'Save Event'}
          </Text>
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
  dateValue: { fontSize: 12, color: '#171717', marginRight: 5 },
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
  notesInput: { minHeight: 80 },
  timeHelper: {flexDirection:'row',justifyContent:'space-between',marginBottom:8},
  timeHelperText: {color:'#A0A0A8',fontSize:11},
  privacyRow: {flexDirection:'row',alignItems:'center',justifyContent:'center',gap:6,marginBottom:12},
  modalBackdrop: {flex:1,backgroundColor:'rgba(0,0,0,0.28)',justifyContent:'center',paddingHorizontal:24},
  dateModal: {backgroundColor:'#FFF',borderRadius:16,padding:20},
  modalTopRow: {flexDirection:'row',alignItems:'center',justifyContent:'space-between',marginBottom:20},
  modalTitle: {fontSize:17,fontWeight:'700',color:'#171717'},
  dateMonthRow: {flexDirection:'row',justifyContent:'space-between',alignItems:'center',marginBottom:12},
  dateMonthTitle: {fontSize:15,fontWeight:'600',color:'#171717'},
  dateGrid: {flexDirection:'row',flexWrap:'wrap'},
  dateCell: {width:'14.2857%',height:39,alignItems:'center',justifyContent:'center'},
  weekday: {fontSize:11,color:'#787882'},
  dateNumberCircle: {width:32,height:32,borderRadius:16,alignItems:'center',justifyContent:'center'},
  dateNumber: {fontSize:13,color:'#171717'},
  selectedDateNumber: {backgroundColor:'#1C1C1E'},
  selectedDateNumberText: {color:'#FFFFFF'},
  modalHint: {marginTop:18,fontSize:11,color:'#92929D',textAlign:'center'},
  timeBackdrop: {flex:1,justifyContent:'flex-end',backgroundColor:'rgba(0,0,0,0.2)'},
  timeSheet: {backgroundColor:'#FFF',borderTopLeftRadius:24,borderTopRightRadius:24,paddingHorizontal:20,paddingBottom:32,paddingTop:10},
  sheetHandle: {width:38,height:4,borderRadius:2,backgroundColor:'#DEDEE4',alignSelf:'center',marginBottom:20},
  sheetTitle: {color:'#171717',fontSize:20,fontWeight:'700'},
  sheetDate: {fontSize:12,color:'#9A9AA3',marginBottom:20},
  activeTimeBox: {backgroundColor:'#171717',borderColor:'#171717'},
  activeTimeText: {color:'#FFFFFF'},
  timeWheelHint: {textAlign:'center',fontSize:12,color:'#85858E',marginTop:10},
  nativeTimePicker: {alignSelf:'center',width:'100%',height:190},
  timeSummary: {textAlign:'center',color:'#66666C',fontSize:12,marginVertical:15},
  pickerContainer: {
    paddingHorizontal: 20,
    paddingVertical: 8,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#EEEEF0',
  },
  pickerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  pickerTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#171717',
  },
  pickerDone: {
    fontSize: 15,
    fontWeight: '600',
    color: '#57068C',
  },
  footer: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 18 },
  privacy: { color: '#A0A0A8', textAlign: 'center', fontSize: 12 },
  saveButton: {
    backgroundColor: '#171717',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
  },
  saveText: { color: '#FFFFFF', fontWeight: '600', fontSize: 15 },
});
