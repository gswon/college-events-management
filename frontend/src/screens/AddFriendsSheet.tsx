import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
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
import { FIGMA_FRIENDS_PREVIEW, FIGMA_USERS, hidePreviewFriend, useHiddenPreviewFriends, type PreviewUser } from '../data/figmaFriendsPreview';
import {
  calendarFriendsApi,
  type Friend,
  type FriendRequest,
} from '../services/calendarFriendsApi';

type Props = { visible: boolean; onClose: () => void; previewProfileId?: string | null };
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
function LiveAddFriendsSheet({ visible, onClose }: Props) {
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
          {!loading && !error && outgoing.length > 0 && (
            <View style={styles.sentBanner}>
              <Feather name="check-circle" size={13} color="#598674" />
              <Text style={styles.sentBannerText}>Friend request sent</Text>
            </View>
          )}
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


/**
 * Figma-only preview. This is a deliberate, isolated visual prototype:
 * no mock users enter the real friends API, and no real friend requests are sent.
 * Set to false when the Backend team provides a searchable user directory.
 */

function FigmaFriendsPreview({ visible, onClose, previewProfileId }: Props) {
  const [search, setSearch] = useState('');
  const [requested, setRequested] = useState<string[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  // Preview-only state: never changes or removes actual Backend friends.
  const [profileUser, setProfileUser] = useState<PreviewUser | null>(null);
  const hiddenFriendIds = useHiddenPreviewFriends();
  useEffect(() => {
    if (visible && previewProfileId) {
      const friend = FIGMA_USERS.find(user => user.id === previewProfileId && user.state === 'friend' && !hiddenFriendIds.includes(user.id));
      setProfileUser(friend ?? null);
    }
  }, [visible, previewProfileId, hiddenFriendIds]);

  const [calendarVisibleById, setCalendarVisibleById] = useState<Record<string, boolean>>({});
  const closePreview = () => {
    if (profileUser) {
      setProfileUser(null);
    } else {
      onClose();
    }
  };
  const removePreviewFriend = (user: PreviewUser) => {
    Alert.alert(
      'Remove friend?',
      `Remove ${user.name} from your preview friends? This will not change the server.`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Remove Friend', style: 'destructive', onPress: () => {
          hidePreviewFriend(user.id);
          setProfileUser(null);
        } },
      ]
    );
  };

  const addFriend = (id: string) => {
    setRequested(previous => previous.includes(id) ? previous : [...previous, id]);
    setNotice('Friend request sent');
  };
  const cancelFriend = (id: string) => {
    setRequested(previous => previous.filter(item => item !== id));
    setNotice(null);
  };
  const resendInvite = () => setNotice('Friend request sent');

  const results = FIGMA_USERS.filter(user =>
    `${user.name} ${user.email}`.toLowerCase().includes(search.trim().toLowerCase())
  );

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={closePreview}>
      <View style={styles.scrim}>
        <Pressable style={StyleSheet.absoluteFill} onPress={closePreview} accessibilityLabel="Close" />
        {profileUser ? (
          <View style={styles.profileSheet}>
            <View style={styles.profileHandle} />
            <Pressable
              style={styles.profileClose}
              onPress={() => setProfileUser(null)}
              accessibilityRole="button"
              accessibilityLabel="Close friend profile"
            >
              <Feather name="x" size={18} color="#8C8C92" />
            </Pressable>
            <View style={[styles.profileAvatar, { backgroundColor: profileUser.color }]}>
              <Text style={styles.profileInitials}>{initials(profileUser.name)}</Text>
            </View>
            <Text style={styles.profileName}>{profileUser.name}</Text>
            <Text style={styles.profileEmail}>{profileUser.email}</Text>
            <View style={styles.profileStatus}>
              <View style={styles.profileStatusDot} />
              <Text style={styles.profileStatusText}>Friends</Text>
            </View>
            <View style={styles.profileRule} />
            <View style={styles.profileActionRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.profileActionTitle}>View Calendar</Text>
                <Text style={styles.profileActionSubtitle}>
                  {calendarVisibleById[profileUser.id] === false ? 'Schedule is hidden' : 'Schedule is visible'}
                </Text>
              </View>
              <Switch
                value={calendarVisibleById[profileUser.id] !== false}
                onValueChange={value => setCalendarVisibleById(prev => ({ ...prev, [profileUser.id]: value }))}
                trackColor={{ false: '#DADADD', true: '#222326' }}
                thumbColor="#FFFFFF"
                accessibilityLabel={`View ${profileUser.name}'s calendar (preview)`}
              />
            </View>
            <View style={styles.profileRule} />
            <Pressable
              style={styles.profileActionRow}
              onPress={() => removePreviewFriend(profileUser)}
              accessibilityRole="button"
              accessibilityLabel={`Remove ${profileUser.name} (preview only)`}
            >
              <View style={{ flex: 1 }}>
                <Text style={styles.profileRemoveTitle}>Remove Friend</Text>
                <Text style={styles.profileActionSubtitle}>Remove calendar access</Text>
              </View>
              <Feather name="chevron-right" size={18} color="#B44E57" />
            </Pressable>
            <View style={styles.profileRule} />
            <Text style={styles.profilePreviewHint}>DESIGN PREVIEW · Changes are not sent to the server</Text>
          </View>
        ) : (
        <View style={styles.sheet}>
          <View style={styles.handle} />
          <View style={styles.headingRow}>
            <View>
              <Text style={styles.eyebrow}>NYU COMMUNITY</Text>
              <Text style={styles.title}>Add Friends</Text>
            </View>
            <Pressable style={styles.closeButton} onPress={closePreview} accessibilityLabel="Close">
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
              accessibilityLabel="Search preview users by name or email"
            />
          </View>
          {notice && (
            <View style={styles.sentBanner}>
              <Feather name="check-circle" size={13} color="#598674" />
              <Text style={styles.sentBannerText}>{notice}</Text>
            </View>
          )}
          <ScrollView
            style={styles.list}
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={styles.listContent}
          >
            {results.length ? results.map((user, index) => {
              const isRequested = requested.includes(user.id);
              return (
                <View key={user.id} style={styles.personRow}>
                  {user.state === 'friend' && !hiddenFriendIds.includes(user.id) ? (
                    <Pressable
                      onPress={() => setProfileUser(user)}
                      onLongPress={() => setProfileUser(user)}
                      delayLongPress={350}
                      accessibilityRole="button"
                      accessibilityLabel={`Open ${user.name} friend profile`}
                      accessibilityHint="Tap or hold to manage this preview friend"
                      style={[styles.avatar, { backgroundColor: user.color }]}
                    >
                      <Text style={styles.initials}>{initials(user.name)}</Text>
                    </Pressable>
                  ) : (
                    <View style={[styles.avatar, { backgroundColor: user.color }]}>
                      <Text style={styles.initials}>{initials(user.name)}</Text>
                    </View>
                  )}
                  <View style={styles.personInfo}>
                    <Text style={styles.name} numberOfLines={1}>{user.name}</Text>
                    <Text style={styles.previewEmail} numberOfLines={1}>{user.email}</Text>
                  </View>
                  {user.state === 'friend' && !hiddenFriendIds.includes(user.id) ? (
                    <Pressable
                      style={styles.statusPill}
                      onPress={() => setProfileUser(user)}
                      onLongPress={() => setProfileUser(user)}
                      accessibilityRole="button"
                      accessibilityLabel={`Manage ${user.name}`}
                    >
                      <Text style={styles.statusText}>Friends</Text>
                    </Pressable>
                  ) : isRequested ? (
                    <View style={styles.requestActions}>
                      <View style={styles.requestedPill}>
                        <Text style={styles.requestedText}>Requested</Text>
                      </View>
                      <View style={styles.previewSecondaryActions}>
                        <Pressable onPress={() => cancelFriend(user.id)} accessibilityRole="button" accessibilityLabel={`Cancel request to ${user.name}`} hitSlop={6}>
                          <Text style={styles.cancelText}>Cancel</Text>
                        </Pressable>
                        <Pressable onPress={resendInvite} accessibilityRole="button" accessibilityLabel={`Resend invite to ${user.name}`} hitSlop={6}>
                          <Text style={styles.resendText}>Resend invite</Text>
                        </Pressable>
                      </View>
                    </View>
                  ) : (
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={`Add ${user.name}`}
                      onPress={() => addFriend(user.id)}
                      style={styles.addButton}
                    >
                      <Text style={styles.addButtonText}>+ Add</Text>
                    </Pressable>
                  )}
                </View>
              );
            }) : (
              <Text style={styles.message}>No matching users.</Text>
            )}
          </ScrollView>
          <Text style={styles.previewDisclosure}>DESIGN PREVIEW · Requests are not sent to the server</Text>
        </View>
        )}
      </View>
    </Modal>
  );
}

export default function AddFriendsSheet(props: Props) {
  return FIGMA_FRIENDS_PREVIEW
    ? <FigmaFriendsPreview {...props} />
    : <LiveAddFriendsSheet {...props} />;
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
  sentBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#EDF4EF', paddingHorizontal: 12, height: 31, borderRadius: 6, marginBottom: 8 },
  sentBannerText: { color: '#658875', fontSize: 11, fontWeight: '500' },
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
  previewEmail: { fontSize: 10, color: '#A0A4AD', marginTop: 6 },
  previewSecondaryActions: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 6 },
  resendText: { fontSize: 10, fontWeight: '600', color: '#9F6DB3' },
  addButton: { height: 32, minWidth: 55, borderWidth: 1, borderColor: '#E3E3E7', backgroundColor: '#FFFFFF', borderRadius: 7, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 9 },
  addButtonText: { fontSize: 11, fontWeight: '600', color: '#292929' },
  previewDisclosure: { color: '#A7ABB3', fontSize: 9, textAlign: 'center', paddingBottom: 8, paddingTop: 4 },
  // Figma Friend Profile Management bottom sheet (Preview-only users).
  profileSheet: { backgroundColor: '#FFF', borderTopLeftRadius: 27, borderTopRightRadius: 27, paddingTop: 11, paddingHorizontal: 24, paddingBottom: 32, minHeight: 390 },
  profileHandle: { alignSelf: 'center', width: 38, height: 4, borderRadius: 4, backgroundColor: '#D9DADD' },
  profileClose: { position: 'absolute', right: 22, top: 22, width: 34, height: 34, borderRadius: 17, backgroundColor: '#F4F4F5', justifyContent: 'center', alignItems: 'center' },
  profileAvatar: { alignSelf: 'center', marginTop: 26, width: 68, height: 68, borderRadius: 34, justifyContent: 'center', alignItems: 'center' },
  profileInitials: { fontSize: 17, fontWeight: '600', color: '#56768D' },
  profileName: { textAlign: 'center', color: '#222', fontSize: 21, fontWeight: '700', marginTop: 17 },
  profileEmail: { textAlign: 'center', color: '#A0A4AC', fontSize: 10, marginTop: 7 },
  profileStatus: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 6, marginTop: 18, marginBottom: 28 },
  profileStatusDot: { backgroundColor: '#649782', width: 6, height: 6, borderRadius: 3 },
  profileStatusText: { color: '#649782', fontSize: 11 },
  profileRule: { height: 1, backgroundColor: '#E8E8EB' },
  profileActionRow: { minHeight: 65, flexDirection: 'row', alignItems: 'center' },
  profileActionTitle: { color: '#242428', fontSize: 13 },
  profileActionSubtitle: { color: '#AAAEB5', fontSize: 10, marginTop: 5 },
  profileRemoveTitle: { color: '#B44E57', fontSize: 13 },
  profilePreviewHint: { color: '#A7ABB3', fontSize: 9, marginTop: 14, textAlign: 'center' },
});
