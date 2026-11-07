import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { loadLocalProfile, saveLocalProfile } from '../services/localProfile';

type Props = { onBack: () => void };

/** Account Settings Figma. Save is device-only until the team supplies a real account/profile update API. */
export default function AccountSettingsScreen({ onBack }: Props) {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [program, setProgram] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let mounted = true;
    loadLocalProfile()
      .then(value => {
        if (!mounted || !value) return;
        setFullName(value.fullName);
        setEmail(value.email);
        setProgram(value.program);
      })
      .catch(() => {
        if (mounted) Alert.alert('Unable to load local settings', 'Your previous device-only settings could not be loaded.');
      })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  async function save() {
    if (saving) return;
    const next = { fullName: fullName.trim(), email: email.trim().toLowerCase(), program: program.trim() };
    if (!next.fullName || !next.email || !next.program) {
      Alert.alert('Missing information', 'Please complete all three fields.');
      return;
    }
    if (!/^[^\s@]+@nyu\.edu$/i.test(next.email)) {
      Alert.alert('NYU email required', 'Enter a valid @nyu.edu email address.');
      return;
    }
    setSaving(true);
    try {
      await saveLocalProfile(next);
      Alert.alert('Saved on this device', 'This is a local prototype setting, not a change to your NYU account. Backend profile editing is not connected.', [
        { text: 'OK', onPress: onBack },
      ]);
    } catch {
      Alert.alert('Save failed', 'Your changes could not be stored on this device.');
    } finally { setSaving(false); }
  }

  return (
    <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Pressable style={styles.back} onPress={onBack} accessibilityRole="button" accessibilityLabel="Back to Profile">
            <Feather name="chevron-left" size={22} color="#191919" />
          </Pressable>
          <Text style={styles.heading}>Account Settings</Text>
          <View style={styles.back} />
        </View>
        <Text style={styles.section}>PERSONAL INFORMATION</Text>
        {loading ? <ActivityIndicator color="#191919" style={{ marginTop: 26 }} /> : (
          <>
            <Text style={styles.label}>Full name</Text>
            <TextInput style={styles.input} value={fullName} onChangeText={setFullName} placeholder="Full name" placeholderTextColor="#B1B4BB" autoCapitalize="words" autoComplete="name" />
            <Text style={styles.label}>NYU email</Text>
            <TextInput style={styles.input} value={email} onChangeText={setEmail} placeholder="netid@nyu.edu" placeholderTextColor="#B1B4BB" keyboardType="email-address" autoCapitalize="none" autoCorrect={false} autoComplete="email" />
            <Text style={styles.label}>Program</Text>
            <TextInput style={styles.input} value={program} onChangeText={setProgram} placeholder="Your program" placeholderTextColor="#B1B4BB" autoCapitalize="sentences" />
            <Pressable style={[styles.button, saving && { opacity: 0.6 }]} onPress={() => void save()} disabled={saving} accessibilityRole="button">
              <Text style={styles.buttonText}>{saving ? 'Saving…' : 'Save Changes'}</Text>
            </Pressable>
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { paddingHorizontal: 22, paddingBottom: 48 },
  header: { height: 66, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 },
  back: { width: 32, minHeight: 32, justifyContent: 'center' },
  heading: { fontSize: 17, fontWeight: '700', color: '#181818' },
  section: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2, color: '#A2A9B8', marginBottom: 17 },
  label: { fontSize: 12, color: '#363636', marginBottom: 8 },
  input: { height: 42, borderWidth: 1, borderColor: '#E0E4EB', borderRadius: 11, paddingHorizontal: 14, color: '#242424', fontSize: 13, marginBottom: 17 },
  button: { height: 45, borderRadius: 10, backgroundColor: '#121212', alignItems: 'center', justifyContent: 'center', marginTop: 7 },
  buttonText: { color: '#FFF', fontSize: 12, fontWeight: '600' },
});
