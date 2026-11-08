import React, { useEffect, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { loadLocalProfile, type LocalProfile } from '../services/localProfile';

type Props = {
  onOpenFriends: () => void;
  onOpenAccountSettings: () => void;
  friendCount?: number;
};

/** Updated Figma Profile. Account data needs the team's authentication API. */
export default function ProfileScreen({ onOpenFriends, onOpenAccountSettings, friendCount = 0 }: Props) {
  const [localProfile, setLocalProfile] = useState<LocalProfile | null>(null);
  useEffect(() => {
    let mounted = true;
    loadLocalProfile()
      .then(profile => { if (mounted) setLocalProfile(profile); })
      .catch(() => { if (mounted) setLocalProfile(null); });
    return () => { mounted = false; };
  }, []);
  const displayName = localProfile?.fullName || 'Account details unavailable';
  const initials = localProfile?.fullName
    ? localProfile.fullName.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase()
    : 'NYU';
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>Your account</Text>
      <Text style={styles.heading}>Profile</Text>
      <Pressable style={styles.identity} onPress={onOpenAccountSettings} accessibilityRole="button" accessibilityLabel="Open Account Settings">
        <View style={styles.avatar}><Text style={styles.avatarText}>{initials}</Text></View>
        <View style={styles.identityText}>
          <Text style={styles.accountName}>{displayName}</Text>
          <Text style={styles.accountEmail}>{localProfile?.email || 'Connect authentication to display your NYU account'}</Text>
          <View style={styles.studentTag}><Text style={styles.studentTagText}>{localProfile?.program || 'NYU Student'}</Text></View>
        </View>
      </Pressable>
      <View style={styles.section}>
        <Text style={styles.sectionLabel}>ACCOUNT</Text>
        <View style={styles.settingRow}>
          <Text style={styles.settingTitle}>Campus</Text>
          <Text style={styles.settingValue}>Not configured</Text>
        </View>
        <Pressable style={styles.settingRow} onPress={onOpenFriends} accessibilityRole="button" accessibilityLabel="Calendar sharing and friends">
          <Text style={styles.settingTitle}>Calendar sharing</Text>
          <Text style={styles.settingValue}>{friendCount} friends</Text>
        </Pressable>
        <Pressable style={styles.settingRow} onPress={() => Alert.alert('Notifications', 'Notification preferences are not connected yet.')} accessibilityRole="button">
          <Text style={styles.settingTitle}>Notifications</Text>
          <Text style={styles.settingValue}>Not configured</Text>
        </Pressable>
      </View>
      <Pressable
        style={styles.logoutButton}
        accessibilityRole="button"
        onPress={() => Alert.alert('Log Out unavailable', 'The backend does not yet provide a login or logout session. No user session was changed.')}
      >
        <Text style={styles.logoutText}>Log Out</Text>
      </Pressable>
      <Text style={styles.footer}>NYU Events · Prototype</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { paddingHorizontal: 24, paddingTop: 30, paddingBottom: 60 },
  eyebrow: { color: '#9398A1', fontSize: 12, marginBottom: 7 },
  heading: { fontSize: 28, fontWeight: '700', color: '#1A1A1A', marginBottom: 30 },
  identity: { borderTopWidth: 1, borderTopColor: '#F0F0F0', paddingVertical: 27, flexDirection: 'row', alignItems: 'center', gap: 16, borderBottomWidth: 1, borderBottomColor: '#E5E5E7' },
  avatar: { width: 60, height: 60, borderRadius: 30, backgroundColor: '#212123', alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: '#FFF', fontSize: 13, fontWeight: '600' },
  identityText: { flex: 1, gap: 5 },
  accountName: { fontSize: 16, fontWeight: '700', color: '#191919' },
  accountEmail: { fontSize: 11, lineHeight: 16, color: '#9C9FA7' },
  studentTag: { alignSelf: 'flex-start', marginTop: 6, borderRadius: 4, borderWidth: 1, borderColor: '#E4E4E7', paddingVertical: 3, paddingHorizontal: 8 },
  studentTagText: { fontSize: 10, color: '#888B93' },
  section: { marginTop: 28 },
  sectionLabel: { fontSize: 11, fontWeight: '600', letterSpacing: 1.3, color: '#969BA5', marginBottom: 14 },
  settingRow: { borderTopWidth: 1, borderTopColor: '#E7E7E9', paddingVertical: 20, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  settingTitle: { color: '#292929', fontSize: 13 },
  settingValue: { color: '#979AA1', fontSize: 11 },
  logoutButton: { marginTop: 26, height: 45, borderRadius: 8, borderWidth: 1, borderColor: '#E7E7E9', alignItems: 'center', justifyContent: 'center' },
  logoutText: { color: '#A8464C', fontSize: 12, fontWeight: '600' },
  footer: { textAlign: 'center', color: '#D0D0D3', marginTop: 17, fontSize: 10 },
});
