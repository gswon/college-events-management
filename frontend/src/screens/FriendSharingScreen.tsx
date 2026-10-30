
import React, { useEffect, useState } from 'react';
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
} from '../services/calendarFriendsApi';

type Sharing = Friend['sharing'];
type SharingKey = keyof Sharing;
type Visibility = Sharing[SharingKey];

type Props = {
  friendId: number;
  friendName: string;
  onBack: () => void;
};

const fields: { key: SharingKey; label: string }[] = [
  { key: 'class', label: 'Class Schedule' },
  { key: 'personal', label: 'Personal Events' },
  { key: 'event', label: 'NYU Events' },
];

const options: Visibility[] = ['HIDDEN', 'BUSY', 'DETAILS'];

export default function FriendSharingScreen({
  friendId,
  friendName,
  onBack,
}: Props) {
  const [settings, setSettings] = useState<Sharing | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;

    calendarFriendsApi
      .getFriendSharing(friendId)
      .then((result) => {
        if (active) {
          setSettings(result);
        }
      })
      .catch((error) => {
        if (active) {
          Alert.alert(
            'Could not load sharing settings',
            error instanceof Error
              ? error.message
              : 'Please try again.'
          );
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [friendId]);

  async function updateSetting(
    key: SharingKey,
    value: Visibility
  ) {
    if (!settings || saving || settings[key] === value) {
      return;
    }

    setSaving(true);

    try {
      await calendarFriendsApi.updateFriendSharing(friendId, {
        [key]: value,
      });

      // Reload the actual saved settings from the backend.
      const latest =
        await calendarFriendsApi.getFriendSharing(friendId);

      setSettings(latest);
    } catch (error) {
      Alert.alert(
        'Update failed',
        error instanceof Error
          ? error.message
          : 'Please try again.'
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      <View style={styles.header}>
        <Pressable
          onPress={onBack}
          accessibilityLabel="Back to Friends"
        >
          <Feather
            name="arrow-left"
            size={24}
            color="#171717"
          />
        </Pressable>

        <Text style={styles.title}>
          Sharing Settings
        </Text>

        <View style={{ width: 24 }} />
      </View>

      <Text style={styles.subtitle}>
        Choose what {friendName} can see from your calendar.
      </Text>

      {loading ? (
        <ActivityIndicator
          color="#57068C"
          style={styles.loader}
        />
      ) : !settings ? (
        <Text style={styles.description}>
          Sharing settings could not be loaded.
          Go back and try again.
        </Text>
      ) : (
        <>
          {fields.map((field) => (
            <View
              key={field.key}
              style={styles.section}
            >
              <Text style={styles.sectionTitle}>
                {field.label}
              </Text>

              {options.map((option) => {
                const selected =
                  settings[field.key] === option;

                return (
                  <Pressable
                    key={option}
                    disabled={saving}
                    onPress={() =>
                      void updateSetting(
                        field.key,
                        option
                      )
                    }
                    style={styles.optionRow}
                  >
                    <Text style={styles.optionText}>
                      {option}
                    </Text>

                    <Feather
                      name={
                        selected
                          ? 'check-circle'
                          : 'circle'
                      }
                      size={22}
                      color={
                        selected
                          ? '#57068C'
                          : '#CCCCCC'
                      }
                    />
                  </Pressable>
                );
              })}
            </View>
          ))}

          {saving && (
            <ActivityIndicator
              color="#57068C"
              style={styles.loader}
            />
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
    paddingTop: 20,
    paddingBottom: 40,
  },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },

  title: {
    fontSize: 21,
    fontWeight: '700',
    color: '#171717',
  },

  subtitle: {
    marginTop: 28,
    marginBottom: 18,
    fontSize: 14,
    lineHeight: 22,
    color: '#92929D',
  },

  loader: {
    marginTop: 30,
  },

  description: {
    color: '#92929D',
    fontSize: 14,
    marginTop: 30,
  },

  section: {
    marginTop: 24,
  },

  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.5,
    color: '#55555C',
    marginBottom: 10,
  },

  optionRow: {
    paddingVertical: 17,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: '#EFEFF1',
  },

  optionText: {
    fontSize: 15,
    color: '#171717',
  },
});
