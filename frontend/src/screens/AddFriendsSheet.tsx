import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import {
  calendarFriendsApi,
  type Friend,
  type FriendRequest,
} from '../services/calendarFriendsApi';

type Props = { visible: boolean; onClose: () => void };
type DirectoryRow = {
  key: string;
  name: string;
  kind: 'friend' | 'requested';
  requestId?: number;
};

const initials = (name: string) =>
  name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();

/**
 * Latest Figma: NYU COMMUNITY / Add Friends bottom sheet.
 * Only existing friends and pending outgoing requests are available until
 * the backend supplies a real user-directory search endpoint.
 */
export default function AddFriendsSheet({ visible, onClose }: Props) {
  const [search, setSearch] = useState('');
  const [friends, setFriends] = useState<Friend[]>([]);
  const [outgoing, setOutgoing] = useState<FriendRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [existing, sent] = await Promise.all([
        calendarFriendsApi.getFriends(),
        calendarFriendsApi.getOutgoingRequests(),
      ]);
      setFriends(existing);
      setOutgoing(sent.filter(request => request.status === 'PENDING'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load friends.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (visible) void load();
  }, [visible, load]);

  const cancelRequest = (requestId: number) => {
    Alert.alert('Cancel friend request?', 'This will withdraw your pending request.', [
      { text: 'Keep Request', style: 'cancel' },
      {
        text: 'Cancel Request',
        style: 'destructive',
        onPress: async () => {
          setCancellingId(requestId);
          try {
            await calendarFriendsApi.cancelFriendRequest(requestId);
            setOutgoing(previous => previous.filter(request => request.id !== requestId));
          } catch (err) {
            Alert.alert('Unable to cancel request', err instanceof Error ? err.message : 'Please try again.');
          } finally {
            setCancellingId(null);
          }
        },
      },
    ]);
  };

  const rows: DirectoryRow[] = [
    ...friends.map(friend => ({
      key: `friend-${friend.user.id}`,
      name: friend.user.display_name,
      kind: 'friend' as const,
    })),
    ...outgoing.map(request => ({
      key: `request-${request.id}`,
      name: request.to_user.display_name,
      kind: 'requested' as const,
      requestId: request.id,
    })),
  ].filter(row => row.name.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.scrim}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Close Add Friends" />
        <View style={styles.sheet}>
          <View style={styles.handle} />
          <View style={styles.headingRow}>
            <View>
              <Text style={styles.eyebrow}>NYU COMMUNITY</Text>
              <Text style={styles.title}>Add Friends</Text>
            </View>
            <Pressable style={styles.closeButton} onPress={onClose} accessibilityLabel="Close">
              <Feather name="x" size={19} color="#888" />
            </Pressable>
          </View>
          <View style={styles.searchBox}>
            <Feather name="search" size={17} color="#A0A3AA" />
            <TextInput
              value={search}
              onChangeText={setSearch}
              placeholder="Search name or NYU email"
              placeholderTextColor="#B0B3B9"
              style={styles.searchInput}
              autoCapitalize="none"
              autoCorrect={false}
              accessibilityLabel="Search existing friends by name"
            />
          </View>
          <ScrollView style={styles.list} keyboardShouldPersistTaps="handled" contentContainerStyle={styles.listContent}>
            {loading ? (
              <ActivityIndicator style={styles.spinner} color="#202020" />
            ) : error ? (
              <Pressable onPress={() => void load()}>
                <Text style={styles.message}>{error} · Tap to retry</Text>
              </Pressable>
            ) : rows.length ? (
              rows.map((row, index) => (
                <View key={row.key} style={styles.personRow}>
                  <View style={[styles.avatar, { backgroundColor: ['#E6EFF5', '#F5EAE5', '#E6F2EC', '#F2E8ED'][index % 4] }]}>
                    <Text style={styles.initials}>{initials(row.name)}</Text>
                  </View>
                  <View style={styles.personInfo}>
                    <Text style={styles.name} numberOfLines={1}>{row.name}</Text>
                    {/* NYU email is not returned by the existing friends API. */}
                  </View>
                  {row.kind === 'friend' ? (
                    <View style={styles.statusPill}><Text style={styles.statusText}>Friends</Text></View>
                  ) : (
                    <View style={styles.requestActions}>
                      <View style={styles.requestedPill}><Text style={styles.requestedText}>Requested</Text></View>
                      <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={`Cancel friend request to ${row.name}`}
                        disabled={cancellingId !== null}
                        onPress={() => row.requestId !== undefined && cancelRequest(row.requestId)}
                        hitSlop={5}
                      >
                        <Text style={styles.cancelText}>{cancellingId === row.requestId ? 'Cancelling…' : 'Cancel'}</Text>
                      </Pressable>
                    </View>
                  )}
                </View>
              ))
            ) : (
              <Text style={styles.message}>
                {search.trim()
                  ? 'No matching friends or sent requests. Searching new NYU users requires a Backend directory API.'
                  : 'No friends or pending requests yet. Adding new users requires a Backend directory API.'}
              </Text>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.28)' },
  sheet: {
    backgroundColor: '#FFF',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    paddingHorizontal: 23,
    paddingTop: 10,
    height: '79%',
  },
  handle: { alignSelf: 'center', backgroundColor: '#D9DADD', width: 38, height: 4, borderRadius: 3, marginBottom: 25 },
  headingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  eyebrow: { color: '#9FA5B1', fontWeight: '600', letterSpacing: 1.2, fontSize: 10, marginBottom: 8 },
  title: { color: '#191919', fontSize: 23, fontWeight: '700' },
  closeButton: { height: 34, width: 34, borderRadius: 17, backgroundColor: '#F4F4F5', alignItems: 'center', justifyContent: 'center' },
  searchBox: { marginTop: 25, marginBottom: 10, height: 45, flexDirection: 'row', borderWidth: 1, borderColor: '#E6E6E7', backgroundColor: '#FAFAFA', borderRadius: 8, alignItems: 'center', paddingHorizontal: 12, gap: 10 },
  searchInput: { flex: 1, fontSize: 12, color: '#222' },
  list: { flex: 1 },
  listContent: { paddingBottom: 25 },
  spinner: { padding: 25 },
  personRow: { minHeight: 72, flexDirection: 'row', alignItems: 'center', gap: 12, borderBottomWidth: 1, borderBottomColor: '#EEEEF0' },
  avatar: { height: 38, width: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  initials: { fontSize: 11, fontWeight: '600', color: '#68727A' },
  personInfo: { flex: 1 },
  name: { fontSize: 13, fontWeight: '600', color: '#252525' },
  statusPill: { backgroundColor: '#F4F4F5', borderRadius: 6, paddingHorizontal: 9, paddingVertical: 7 },
  statusText: { fontSize: 10, color: '#8E929B' },
  requestActions: { alignItems: 'center', gap: 7 },
  requestedPill: { backgroundColor: '#F8F8F9', borderWidth: 1, borderColor: '#E5E5E8', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 6 },
  requestedText: { fontSize: 10, color: '#777B83' },
  cancelText: { color: '#A0A3AA', fontSize: 10 },
  message: { paddingVertical: 20, color: '#999BA4', fontSize: 12, lineHeight: 18 },
});
