
import React from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';

type Props = {
  onOpenFriends: () => void;
  friendCount?: number;
};

export default function ProfileScreen({
  onOpenFriends,
  friendCount = 0,
}: Props) {
  const settings = [
    {
      title: 'Friends',
      subtitle: `${friendCount} added · Search and add friends`,
      icon: 'users' as const,
      onPress: onOpenFriends,
    },
    {
      title: 'Account Settings',
      subtitle: 'Name, email, and program',
      icon: 'settings' as const,
      onPress: () =>
        Alert.alert('Account Settings', 'Account settings are not connected yet.'),
    },
    {
      title: 'Reset Password',
      subtitle: 'Update your account password',
      icon: 'key' as const,
      onPress: () =>
        Alert.alert('Reset Password', 'Password reset is not connected yet.'),
    },
    {
      title: 'Notifications',
      subtitle: 'Push & email',
      icon: 'bell' as const,
      onPress: () =>
        Alert.alert('Notifications', 'Notification settings are not connected yet.'),
    },
  ];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      <View style={styles.profileHeader}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>JC</Text>
        </View>

        <Text style={styles.name}>Joanna Kim</Text>
        <Text style={styles.university}>New York University</Text>
        <Text style={styles.program}>BFA · Interactive Media Arts</Text>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.stat}>
          <Text style={styles.statValue}>4</Text>
          <Text style={styles.statLabel}>Courses</Text>
        </View>

        <View style={[styles.stat, styles.statBorder]}>
          <Text style={styles.statValue}>2</Text>
          <Text style={styles.statLabel}>Shared</Text>
        </View>

        <View style={styles.stat}>
          <Text style={styles.statValue}>12</Text>
          <Text style={styles.statLabel}>Events</Text>
        </View>
      </View>

      <Pressable
        style={styles.importButton}
        onPress={() =>
          Alert.alert(
            'Import Class Schedule',
            'Class schedule import is not connected yet.'
          )
        }
      >
        <Feather name="upload" size={17} color="#171717" />
        <Text style={styles.importText}>Import Class Schedule</Text>
      </Pressable>

      <View style={styles.settingsList}>
        {settings.map(item => (
          <Pressable
            key={item.title}
            style={styles.settingsRow}
            onPress={item.onPress}
          >
            <View style={styles.settingsIcon}>
              <Feather name={item.icon} size={17} color="#555555" />
            </View>

            <View style={styles.settingsText}>
              <Text style={styles.settingsTitle}>{item.title}</Text>
              <Text style={styles.settingsSubtitle}>
                {item.subtitle}
              </Text>
            </View>

            <Feather name="chevron-right" size={21} color="#C6C6C8" />
          </Pressable>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 28,
    paddingBottom: 36,
  },
  profileHeader: {
    alignItems: 'center',
    marginTop: 16,
    marginBottom: 24,
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#111111',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 17,
  },
  avatarText: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '600',
  },
  name: {
    fontSize: 18,
    fontWeight: '700',
    color: '#171717',
  },
  university: {
    fontSize: 13,
    color: '#798194',
    marginTop: 6,
  },
  program: {
    fontSize: 11,
    color: '#9BA3B2',
    marginTop: 6,
  },
  statsRow: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: '#F3F3F4',
    paddingTop: 17,
    marginBottom: 22,
  },
  stat: {
    flex: 1,
    alignItems: 'center',
  },
  statBorder: {
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderColor: '#F4F4F5',
  },
  statValue: {
    fontSize: 16,
    fontWeight: '700',
    color: '#171717',
  },
  statLabel: {
    fontSize: 10,
    color: '#A0A8B8',
    marginTop: 4,
  },
  importButton: {
    height: 48,
    borderWidth: 1,
    borderColor: '#E7E7EA',
    borderRadius: 13,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 9,
  },
  importText: {
    color: '#252525',
    fontSize: 13,
    fontWeight: '600',
  },
  settingsList: {
    marginTop: 24,
  },
  settingsRow: {
    minHeight: 67,
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#F3F3F4',
    gap: 13,
  },
  settingsIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    backgroundColor: '#F5F5F5',
    alignItems: 'center',
    justifyContent: 'center',
  },
  settingsText: {
    flex: 1,
    gap: 4,
  },
  settingsTitle: {
    fontSize: 14,
    fontWeight: '500',
    color: '#202020',
  },
  settingsSubtitle: {
    fontSize: 11,
    color: '#9AA3B4',
  },
});
