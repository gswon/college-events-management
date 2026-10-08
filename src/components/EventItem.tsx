import { View, Text, StyleSheet } from 'react-native';
import { HomeEvent } from '../data/events';
import { dateLabel, eventTime } from '../date';
export function EventItem({ event, now, last }: { event: HomeEvent; now: Date; last: boolean }) {
  return <View style={[styles.row, !last && styles.divider]}>
    <Text style={styles.date}>{event.designDate ?? dateLabel(event.start_at, now)}</Text>
    <View style={styles.content}>
      <Text style={styles.title}>{event.title}</Text>
      <Text style={styles.meta}>{event.is_all_day ? 'All day' : eventTime(event.start_at)}{event.location_name ? ` · ${event.location_name}` : ''}</Text>
    </View>
  </View>;
}
const styles = StyleSheet.create({
  row: { flexDirection: 'row', paddingVertical: 12, minHeight: 60 },
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#E4E7EC' },
  date: { width: 67, flexShrink: 0, color: '#929DB0', fontSize: 11, lineHeight: 13, fontWeight: '600', paddingTop: 2 },
  content: { flex: 1, minWidth: 0 },
  title: { fontSize: 14, lineHeight: 20, fontWeight: '600', color: '#111111' },
  meta: { fontSize: 12, lineHeight: 18, color: '#929DB0', marginTop: 2 },
});
