import { StatusBar, View, Text, ScrollView, StyleSheet } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { BottomTabBar } from './src/components/BottomTabBar';
import { EventItem } from './src/components/EventItem';
import { demoEvents, demoNow, demoUser } from './src/data/events';
import { greeting, headerDate } from './src/date';
export default function App() {
  return <SafeAreaProvider>
    <StatusBar barStyle="dark-content" backgroundColor="#FFFFFF" />
    <SafeAreaView style={styles.screen} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View style={styles.heading}>
            <Text style={styles.date}>{headerDate(demoNow)}</Text>
            <Text style={styles.greeting}>{greeting(demoNow)}{'\n'}{demoUser.display_name}</Text>
          </View>
          <View style={styles.avatar} accessibilityLabel="Joanna's avatar"><Text style={styles.initials}>{demoUser.initials}</Text></View>
        </View>
        <Text style={styles.section}>CAMPUS EVENTS</Text>
        {demoEvents.map((event, index) => <EventItem key={event.id} event={event} now={demoNow} last={index === demoEvents.length - 1} />)}
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
});
