import { View, Text, Pressable, StyleSheet, Alert } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
const tabs = [ { label: 'Home', icon: 'home' }, { label: 'Calendar', icon: 'calendar' }, { label: 'Events', icon: 'compass' }, { label: 'Profile', icon: 'user' } ] as const;
export function BottomTabBar() {
  const { bottom } = useSafeAreaInsets();
  return <View style={[styles.bar, { paddingBottom: Math.max(bottom, 12) }]}>
    {tabs.map(tab => <Pressable key={tab.label} accessibilityRole="tab" accessibilityLabel={tab.label} accessibilityState={{ selected: tab.label === 'Home' }}
      onPress={() => { if (tab.label !== 'Home') Alert.alert(tab.label, 'This screen is pending. This build implements the two Home designs only.'); }}
      style={({ pressed }) => [styles.tab, { opacity: pressed ? 0.55 : 1 }]}>
      <Feather name={tab.icon} size={21} color={tab.label === 'Home' ? '#111111' : '#BABABA'} />
      <Text style={[styles.label, tab.label === 'Home' && styles.active]}>{tab.label}</Text>
    </Pressable>)}
  </View>;
}
const styles = StyleSheet.create({
  bar: { flexDirection: 'row', borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#E4E7EC', backgroundColor: '#FFFFFF', paddingTop: 8 },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 44, gap: 4 },
  label: { fontSize: 11, color: '#BABABA' }, active: { color: '#111111', fontWeight: '600' },
});
