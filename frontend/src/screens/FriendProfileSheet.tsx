import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { calendarFriendsApi } from '../services/calendarFriendsApi';

type Props = {
  friend: { id: number; name: string } | null;
  calendarVisible: boolean;
  onToggleCalendar: (visible: boolean) => void;
  onRemoved: (friendId: number) => void;
  onClose: () => void;
};

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
}

/** Latest Figma: friend profile / management bottom sheet. */
export default function FriendProfileSheet({
  friend,
  calendarVisible,
  onToggleCalendar,
  onRemoved,
  onClose,
}: Props) {
  const [removing, setRemoving] = useState(false);

  function confirmRemove() {
    if (!friend || removing) return;
    const selected = friend;
    Alert.alert('Remove friend?', `Remove ${selected.name} from your friends?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove Friend',
        style: 'destructive',
        onPress: async () => {
          setRemoving(true);
          try {
            await calendarFriendsApi.removeFriend(selected.id);
            onRemoved(selected.id);
            onClose();
          } catch (error) {
            Alert.alert('Unable to remove friend', error instanceof Error ? error.message : 'Please try again.');
          } finally {
            setRemoving(false);
          }
        },
      },
    ]);
  }

  return (
    <Modal visible={friend !== null} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.scrim}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Close friend profile" />
        <View style={styles.sheet}>
          <View style={styles.handle} />
          <Pressable style={styles.closeButton} onPress={onClose} accessibilityLabel="Close friend profile">
            <Feather name="x" size={19} color="#909097" />
          </Pressable>
          <View style={styles.avatar}><Text style={styles.avatarText}>{friend ? initials(friend.name) : ''}</Text></View>
          <Text style={styles.name}>{friend?.name ?? ''}</Text>
          {/* The current friends API has no email field; do not fabricate one. */}
          <View style={styles.friendStatus}><View style={styles.statusDot} /><Text style={styles.statusText}>Friends</Text></View>
          <View style={styles.rule} />
          <View style={styles.settingRow}>
            <View style={styles.settingDetails}>
              <Text style={styles.settingTitle}>View Calendar</Text>
              <Text style={styles.settingSub}>Include in shared schedule</Text>
            </View>
            <Switch
              value={calendarVisible}
              onValueChange={onToggleCalendar}
              trackColor={{ false: '#DDDDE0', true: '#2B2B2D' }}
              thumbColor="#FFFFFF"
              accessibilityLabel={`Show ${friend?.name ?? 'friend'} in shared calendar`}
            />
          </View>
          <View style={styles.rule} />
          <Pressable style={styles.removeRow} disabled={removing} onPress={confirmRemove} accessibilityRole="button" accessibilityLabel="Remove friend">
            <View style={styles.settingDetails}>
              <Text style={styles.removeTitle}>Remove Friend</Text>
              <Text style={styles.settingSub}>Remove from your friends list</Text>
            </View>
            {removing ? <ActivityIndicator color="#B44F56" /> : <Feather name="chevron-right" size={19} color="#B44F56" />}
          </Pressable>
          <View style={styles.rule} />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.28)' },
  sheet: { backgroundColor: '#FFFFFF', borderTopLeftRadius: 27, borderTopRightRadius: 27, paddingTop: 11, paddingHorizontal: 24, paddingBottom: 42, minHeight: 400 },
  handle: { alignSelf: 'center', width: 38, height: 4, borderRadius: 3, backgroundColor: '#DBDCE0' },
  closeButton: { position: 'absolute', right: 23, top: 23, height: 34, width: 34, borderRadius: 17, backgroundColor: '#F4F4F5', justifyContent: 'center', alignItems: 'center' },
  avatar: { alignSelf: 'center', width: 68, height: 68, borderRadius: 34, marginTop: 26, justifyContent: 'center', alignItems: 'center', backgroundColor: '#E5EFF5' },
  avatarText: { color: '#56778A', fontSize: 18, fontWeight: '600' },
  name: { color: '#222222', fontWeight: '700', fontSize: 22, textAlign: 'center', marginTop: 17 },
  friendStatus: { alignSelf: 'center', flexDirection: 'row', gap: 6, alignItems: 'center', marginTop: 18, marginBottom: 27 },
  statusDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#679783' },
  statusText: { color: '#679783', fontSize: 11 },
  rule: { backgroundColor: '#EBEBEE', height: 1 },
  settingRow: { minHeight: 72, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  settingDetails: { flex: 1 },
  settingTitle: { color: '#2B2B2D', fontSize: 14, fontWeight: '500' },
  settingSub: { color: '#A1A3A9', fontSize: 11, marginTop: 5 },
  removeRow: { minHeight: 73, flexDirection: 'row', alignItems: 'center' },
  removeTitle: { color: '#B44F56', fontSize: 14, fontWeight: '500' },
});
