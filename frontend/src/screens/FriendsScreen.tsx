
import React, { useCallback, useEffect, useState } from 'react';
import FriendCalendarScreen from './FriendCalendarScreen';
import FriendSharingScreen from './FriendSharingScreen';
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
import {
  calendarFriendsApi,
  type Friend,
  type FriendRequest,
} from '../services/calendarFriendsApi';

type Props = {
  onBack: () => void;
};

export default function FriendsScreen({ onBack }: Props) {
  const [friends, setFriends] = useState<Friend[]>([]);
  const [selectedFriend, setSelectedFriend] = useState<Friend | null>(null);
  const [sharingFriend, setSharingFriend] = useState<Friend | null>(null);
  const [requests, setRequests] = useState<FriendRequest[]>([]);
  const [outgoingRequests, setOutgoingRequests] = useState<FriendRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyRequestId, setBusyRequestId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);

      const [friendData, requestData, outgoingData] = await Promise.all([
        calendarFriendsApi.getFriends(),
        calendarFriendsApi.getIncomingRequests(),
        calendarFriendsApi.getOutgoingRequests(),
      ]);

      setFriends(friendData);
      setRequests(
        requestData.filter((request) => request.status === 'PENDING')
      );
      setOutgoingRequests(
        outgoingData.filter((request) => request.status === 'PENDING')
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Could not load friends.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  function confirmRemoveFriend(friend: Friend) {
    Alert.alert(
      'Remove Friend',
      `Remove ${friend.user.display_name} from your friends?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            try {
              await calendarFriendsApi.removeFriend(friend.user.id);
              await loadData();
            } catch (error) {
              Alert.alert(
                'Remove failed',
                error instanceof Error
                  ? error.message
                  : 'Could not remove this friend.'
              );
            }
          },
        },
      ]
    );
  }

  function confirmCancelRequest(request: FriendRequest) {
    Alert.alert(
      'Cancel Friend Request',
      `Cancel your request to ${request.to_user.display_name}?`,
      [
        { text: 'Keep Request', style: 'cancel' },
        {
          text: 'Cancel Request',
          style: 'destructive',
          onPress: async () => {
            if (busyRequestId !== null) return;
            setBusyRequestId(request.id);

            try {
              await calendarFriendsApi.cancelFriendRequest(request.id);
              await loadData();
            } catch (error) {
              Alert.alert(
                'Cancellation failed',
                error instanceof Error
                  ? error.message
                  : 'Could not cancel this request.'
              );
            } finally {
              setBusyRequestId(null);
            }
          },
        },
      ]
    );
  }

  async function respondToRequest(
    requestId: number,
    action: 'accept' | 'decline'
  ) {
    if (busyRequestId !== null) return;

    setBusyRequestId(requestId);

    try {
      if (action === 'accept') {
        await calendarFriendsApi.acceptFriendRequest(requestId);
      } else {
        await calendarFriendsApi.declineFriendRequest(requestId);
      }

      await loadData();
    } catch (err) {
      Alert.alert(
        'Something went wrong',
        err instanceof Error ? err.message : 'Please try again.'
      );
    } finally {
      setBusyRequestId(null);
    }
  }

  if (sharingFriend) {
    return (
      <FriendSharingScreen
        friendId={sharingFriend.user.id}
        friendName={sharingFriend.user.display_name}
        onBack={() => {
          setSharingFriend(null);
          void loadData();
        }}
      />
    );
  }

  if (selectedFriend) {
    return (
      <FriendCalendarScreen
        friendId={selectedFriend.user.id}
        friendName={selectedFriend.user.display_name}
        onBack={() => setSelectedFriend(null)}
      />
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      <View style={styles.header}>
        <Pressable
          onPress={onBack}
          style={styles.backButton}
          accessibilityLabel="Back to Profile"
        >
          <Feather name="arrow-left" size={23} color="#191919" />
        </Pressable>

        <Text style={styles.headerTitle}>Friends</Text>

        <Pressable
          onPress={() => {
            setLoading(true);
            void loadData();
          }}
          accessibilityLabel="Refresh friends"
        >
          <Feather name="refresh-cw" size={20} color="#191919" />
        </Pressable>
      </View>

      <Text style={styles.subtitle}>
        Connect with friends and share your schedule.
      </Text>

      <Pressable
        style={styles.searchBox}
        onPress={() =>
          Alert.alert(
            'Search unavailable',
            'The backend team still needs to add the user search API.'
          )
        }
      >
        <Feather name="search" size={19} color="#999999" />
        <Text style={styles.searchPlaceholder}>
          Search and add friends
        </Text>
      </Pressable>

      {loading ? (
        <ActivityIndicator
          size="large"
          color="#57068C"
          style={styles.loader}
        />
      ) : error ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>{error}</Text>
          <Pressable onPress={() => void loadData()}>
            <Text style={styles.retryText}>Try again</Text>
          </Pressable>
        </View>
      ) : (
        <>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>FRIEND REQUESTS</Text>
            <Text style={styles.count}>{requests.length}</Text>
          </View>

          {requests.length === 0 ? (
            <Text style={styles.emptyText}>
              No pending friend requests.
            </Text>
          ) : (
            requests.map((request) => (
              <View key={request.id} style={styles.personRow}>
                <View style={styles.avatar}>
                  <Text style={styles.avatarText}>
                    {request.from_user.display_name
                      .split(' ')
                      .map((part) => part[0])
                      .slice(0, 2)
                      .join('')
                      .toUpperCase()}
                  </Text>
                </View>

                <View style={styles.personInfo}>
                  <Text style={styles.personName}>
                    {request.from_user.display_name}
                  </Text>
                  <Text style={styles.personDescription}>
                    Wants to be friends
                  </Text>
                </View>

                <Pressable
                  style={styles.acceptButton}
                  disabled={busyRequestId !== null}
                  onPress={() =>
                    void respondToRequest(request.id, 'accept')
                  }
                >
                  <Feather name="check" size={19} color="#FFFFFF" />
                </Pressable>

                <Pressable
                  style={styles.declineButton}
                  disabled={busyRequestId !== null}
                  onPress={() =>
                    void respondToRequest(request.id, 'decline')
                  }
                >
                  <Feather name="x" size={19} color="#444444" />
                </Pressable>
              </View>
            ))
          )}

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>SENT REQUESTS</Text>
            <Text style={styles.count}>{outgoingRequests.length}</Text>
          </View>

          {outgoingRequests.length === 0 ? (
            <Text style={styles.emptyText}>
              No pending sent requests.
            </Text>
          ) : (
            outgoingRequests.map((request) => (
              <View key={request.id} style={styles.personRow}>
                <View style={styles.avatar}>
                  <Text style={styles.avatarText}>
                    {request.to_user.display_name
                      .split(' ')
                      .map((part) => part[0])
                      .slice(0, 2)
                      .join('')
                      .toUpperCase()}
                  </Text>
                </View>

                <View style={styles.personInfo}>
                  <Text style={styles.personName}>
                    {request.to_user.display_name}
                  </Text>
                  <Text style={styles.personDescription}>
                    Request pending
                  </Text>
                </View>

                <Pressable
                  disabled={busyRequestId !== null}
                  onPress={() => confirmCancelRequest(request)}
                  accessibilityLabel={`Cancel request to ${request.to_user.display_name}`}
                >
                  <Text style={{ color: '#B3261E', fontSize: 13, fontWeight: '600' }}>
                    Cancel
                  </Text>
                </Pressable>
              </View>
            ))
          )}

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>MY FRIENDS</Text>
            <Text style={styles.count}>{friends.length}</Text>
          </View>

          {friends.length === 0 ? (
            <Text style={styles.emptyText}>
              You haven't added any friends yet.
            </Text>
          ) : (
            friends.map((friend) => (
              <Pressable
                key={friend.user.id}
                style={styles.personRow}
                onPress={() => setSelectedFriend(friend)}
              >
                <View style={styles.avatar}>
                  <Text style={styles.avatarText}>
                    {friend.user.display_name
                      .split(' ')
                      .map((part) => part[0])
                      .slice(0, 2)
                      .join('')
                      .toUpperCase()}
                  </Text>
                </View>

                <View style={styles.personInfo}>
                  <Text style={styles.personName}>
                    {friend.user.display_name}
                  </Text>
                  <Text style={styles.personDescription}>
                    Added friend
                  </Text>
                </View>

                <Pressable
                  onPress={(event) => {
                    event.stopPropagation();
                    setSharingFriend(friend);
                  }}
                  accessibilityLabel={`Sharing settings for ${friend.user.display_name}`}
                  hitSlop={8}
                  style={styles.removeFriendButton}
                >
                  <Feather name="shield" size={20} color="#57068C" />
                </Pressable>
                <Pressable
                  onPress={(event) => {
                    event.stopPropagation();
                    confirmRemoveFriend(friend);
                  }}
                  accessibilityLabel={`Remove ${friend.user.display_name}`}
                  hitSlop={8}
                  style={styles.removeFriendButton}
                >
                  <Feather name="more-horizontal" size={22} color="#999999" />
                </Pressable>
                <Feather
                  name="chevron-right"
                  size={21}
                  color="#999999"
                />
              </Pressable>
            ))
          )}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 18,
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  backButton: {
    paddingVertical: 8,
    paddingRight: 12,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#191919',
  },
  subtitle: {
    marginTop: 22,
    color: '#888888',
    fontSize: 14,
  },
  searchBox: {
    marginTop: 25,
    height: 52,
    paddingHorizontal: 16,
    borderWidth: 1,
    borderColor: '#E5E5E5',
    borderRadius: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  searchPlaceholder: {
    color: '#A0A0A0',
    fontSize: 14,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 34,
    marginBottom: 14,
  },
  sectionTitle: {
    color: '#9999A5',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.5,
  },
  count: {
    color: '#9999A5',
    fontSize: 13,
  },
  personRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#F0F0F0',
    gap: 12,
  },
  avatar: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: '#F0ECF4',
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#57068C',
  },
  removeFriendButton: {
    padding: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  personInfo: {
    flex: 1,
  },
  personName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#191919',
  },
  personDescription: {
    marginTop: 4,
    fontSize: 12,
    color: '#9C9CA5',
  },
  acceptButton: {
    width: 36,
    height: 36,
    borderRadius: 9,
    backgroundColor: '#57068C',
    justifyContent: 'center',
    alignItems: 'center',
  },
  declineButton: {
    width: 36,
    height: 36,
    borderRadius: 9,
    backgroundColor: '#F1F1F1',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loader: {
    marginTop: 50,
  },
  emptyState: {
    alignItems: 'center',
    marginTop: 40,
  },
  emptyText: {
    color: '#9C9CA5',
    fontSize: 13,
    marginVertical: 8,
  },
  retryText: {
    color: '#57068C',
    fontWeight: '600',
    marginTop: 10,
  },
});
