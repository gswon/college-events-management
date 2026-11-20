import { useState } from 'react';
import { authApi, type AuthSession } from '../services/authApi';
import { saveSession } from '../services/authSession';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

type AuthMode = 'login' | 'signup' | 'verify';

/**
 * Design-only authentication screen based on the supplied Nov 2026 Figma.
 * No credentials are sent or stored: the backend currently lacks auth endpoints.
 */
type AuthScreenProps = {
  onAuthenticated?: (session: AuthSession) => void;
};

export default function AuthScreen({
  onAuthenticated,
}: AuthScreenProps) {
  const [mode, setMode] = useState<AuthMode>('login');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [busy, setBusy] = useState(false);

  function unavailable(action: string) {
    Alert.alert(
      `${action} unavailable`,
      'The authentication API has not been provided by the Backend team. No account or session was created or changed.',
    );
  }

  async function handleAuth() {
    if (busy) return;

    const normalizedEmail = email.trim().toLowerCase();

    if (!normalizedEmail.endsWith('@nyu.edu')) {
      Alert.alert('Invalid email', 'Please use your @nyu.edu email.');
      return;
    }

    if (!password) {
      Alert.alert('Missing password', 'Please enter your password.');
      return;
    }

    if (mode === 'signup') {
      if (!fullName.trim()) {
        Alert.alert('Missing name', 'Please enter your full name.');
        return;
      }
      if (password !== confirmPassword) {
        Alert.alert('Password mismatch', 'Passwords do not match.');
        return;
      }
    }

    setBusy(true);

    try {
      if (mode === 'signup') {
        await authApi.signup(normalizedEmail, password, fullName.trim());
        setEmail(normalizedEmail);
        setVerificationCode('');
        setMode('verify');
        Alert.alert('Check your email', 'Enter the verification code sent to your NYU email.');
      } else {
        const session = await authApi.login(normalizedEmail, password);
        await saveSession(session);
        onAuthenticated?.(session);
        if (!onAuthenticated) {
          Alert.alert('Success', 'You are now logged in.');
        }
      }
    } catch (error) {
      Alert.alert(
        'Authentication failed',
        error instanceof Error ? error.message : 'Please try again.'
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleVerification() {
    if (busy) return;

    if (!verificationCode.trim()) {
      Alert.alert('Missing code', 'Please enter your verification code.');
      return;
    }

    setBusy(true);
    try {
      const session = await authApi.verifyEmail(
        email.trim().toLowerCase(),
        verificationCode.trim()
      );
      await saveSession(session);
      onAuthenticated?.(session);
      if (!onAuthenticated) {
        Alert.alert('Success', 'Your email is verified and you are logged in.');
      }
    } catch (error) {
      Alert.alert(
        'Verification failed',
        error instanceof Error ? error.message : 'Please try again.'
      );
    } finally {
      setBusy(false);
    }
  }

  async function resendVerification() {
    if (busy) return;
    setBusy(true);
    try {
      await authApi.resendVerification(email.trim().toLowerCase());
      Alert.alert('Email sent', 'Please check your NYU inbox.');
    } catch (error) {
      Alert.alert(
        'Unable to resend',
        error instanceof Error ? error.message : 'Please try again.'
      );
    } finally {
      setBusy(false);
    }
  }

  if (mode === 'verify') {
    return (
      <SafeAreaView style={styles.screen}>
        <KeyboardAvoidingView
          style={styles.flex}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
          >
            <View style={styles.brandIcon}>
              <Text style={styles.brandIconText}>NYU</Text>
            </View>
            <Text style={styles.eyebrow}>ONE MORE STEP</Text>
            <Text style={styles.heading}>Verify Email</Text>
            <Text style={styles.tagline}>
              Enter the code sent to {email.trim().toLowerCase()}.
            </Text>

            <View style={[styles.fieldGroup, { marginTop: 40 }]}>
              <Text style={styles.fieldLabel}>Verification Code</Text>
              <TextInput
                style={styles.field}
                value={verificationCode}
                onChangeText={setVerificationCode}
                placeholder="Enter verification code"
                placeholderTextColor="#B7B7BE"
                autoCapitalize="none"
                autoCorrect={false}
                accessibilityLabel="Verification code"
              />
            </View>

            <Pressable
              style={styles.primaryButton}
              onPress={handleVerification}
              disabled={busy}
              accessibilityRole="button"
            >
              <Text style={styles.primaryButtonText}>
                {busy ? 'Please wait...' : 'Verify Email'}
              </Text>
            </Pressable>

            <Pressable
              style={styles.footerSwitch}
              onPress={resendVerification}
              disabled={busy}
              accessibilityRole="button"
            >
              <Text style={styles.footerLink}>Resend Code</Text>
            </Pressable>

            <Pressable
              style={styles.footerSwitch}
              onPress={() => setMode('login')}
              disabled={busy}
              accessibilityRole="button"
            >
              <Text style={styles.footerLink}>Back to Log In</Text>
            </Pressable>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  const signup = mode === 'signup';

  return (
    <SafeAreaView style={styles.screen} edges={['top', 'bottom', 'left', 'right']}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.brandIcon}>
            <Text style={styles.brandIconText}>NYU</Text>
          </View>
          <Text style={styles.eyebrow}>WELCOME TO CAMPUS</Text>
          <Text style={styles.heading}>NYU Events</Text>
          <Text style={styles.tagline}>Your campus, your calendar.</Text>

          <View style={styles.tabs}>
            <Pressable
              style={[styles.tab, !signup && styles.tabSelected]}
              accessibilityRole="tab"
              accessibilityState={{ selected: !signup }}
              onPress={() => setMode('login')}
            >
              <Text style={[styles.tabText, !signup && styles.tabTextSelected]}>Log In</Text>
            </Pressable>
            <Pressable
              style={[styles.tab, signup && styles.tabSelected]}
              accessibilityRole="tab"
              accessibilityState={{ selected: signup }}
              onPress={() => setMode('signup')}
            >
              <Text style={[styles.tabText, signup && styles.tabTextSelected]}>Sign Up</Text>
            </Pressable>
          </View>

          {signup && (
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Full Name</Text>
              <TextInput
                style={styles.field}
                value={fullName}
                onChangeText={setFullName}
                placeholder="Joanna Chen"
                placeholderTextColor="#B7B7BE"
                autoCapitalize="words"
                autoComplete="name"
                returnKeyType="next"
                accessibilityLabel="Full name"
              />
            </View>
          )}

          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>{signup ? 'NYU Email Address' : 'Email Address'}</Text>
            <TextInput
              style={styles.field}
              value={email}
              onChangeText={setEmail}
              placeholder="netid@nyu.edu"
              placeholderTextColor="#B7B7BE"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              autoComplete="email"
              textContentType="emailAddress"
              accessibilityLabel="NYU email address"
            />
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>Password</Text>
            <TextInput
              style={styles.field}
              value={password}
              onChangeText={setPassword}
              placeholder="Enter your password"
              placeholderTextColor="#B7B7BE"
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              textContentType={signup ? 'newPassword' : 'password'}
              accessibilityLabel="Password"
            />
          </View>

          {signup ? (
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Confirm Password</Text>
              <TextInput
                style={styles.field}
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                placeholder="Re-enter your password"
                placeholderTextColor="#B7B7BE"
                secureTextEntry
                autoCapitalize="none"
                autoCorrect={false}
                textContentType="newPassword"
                accessibilityLabel="Confirm password"
              />
            </View>
          ) : (
            <Pressable
              style={styles.forgotRow}
              onPress={() => unavailable('Password reset')}
              accessibilityRole="button"
            >
              <Text style={styles.forgotText}>Forgot Password?</Text>
            </Pressable>
          )}

          <Pressable
            style={styles.primaryButton}
            onPress={handleAuth}
            disabled={busy}
            accessibilityRole="button"
          >
            <Text style={styles.primaryButtonText}>{busy ? 'Please wait...' : signup ? 'Create Account' : 'Log In'}</Text>
          </Pressable>

          <View style={styles.orRow}>
            <View style={styles.orLine} />
            <Text style={styles.orText}>or</Text>
            <View style={styles.orLine} />
          </View>

          <Pressable
            style={styles.googleButton}
            onPress={() => unavailable('Google sign-in')}
            accessibilityRole="button"
          >
            <Text style={styles.googleG}>G</Text>
            <Text style={styles.googleButtonText}>Continue with Google</Text>
          </Pressable>

          <View style={styles.footerSwitch}>
            <Text style={styles.footerMuted}>
              {signup ? 'Already have an account? ' : "Don't have an account? "}
            </Text>
            <Pressable onPress={() => setMode(signup ? 'login' : 'signup')} accessibilityRole="button">
              <Text style={styles.footerLink}>{signup ? 'Log In' : 'Sign Up'}</Text>
            </Pressable>
          </View>

          {!signup && (
            <View style={styles.disclaimerWrap}>
              <Text style={styles.disclaimer}>
                Use your NYU account to keep your campus events in one place.
              </Text>
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#FFFFFF' },
  flex: { flex: 1 },
  scrollContent: { flexGrow: 1, paddingHorizontal: 26, paddingTop: 42, paddingBottom: 92 },
  brandIcon: { height: 39, width: 39, borderRadius: 8, backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center', marginBottom: 30 },
  brandIconText: { color: '#FFFFFF', fontSize: 10, fontWeight: '700' },
  eyebrow: { fontSize: 10, fontWeight: '600', color: '#9CA3AF', letterSpacing: 2, marginBottom: 6 },
  heading: { fontSize: 32, fontWeight: '700', color: '#19191B', letterSpacing: -1.2 },
  tagline: { fontSize: 12, color: '#9CA3AF', marginTop: 10 },
  tabs: { flexDirection: 'row', marginTop: 39, marginBottom: 26, borderBottomColor: '#E8E8EB', borderBottomWidth: 1 },
  tab: { width: '50%', paddingVertical: 14, alignItems: 'center', marginBottom: -1, borderBottomWidth: 2, borderBottomColor: 'transparent' },
  tabSelected: { borderBottomColor: '#1E1E20' },
  tabText: { color: '#A8ABB2', fontSize: 12 },
  tabTextSelected: { color: '#1E1E20', fontWeight: '600' },
  fieldGroup: { marginBottom: 19 },
  fieldLabel: { color: '#38383D', fontSize: 12, fontWeight: '600', marginBottom: 10 },
  field: { borderWidth: 1, borderColor: '#E4E5E8', borderRadius: 9, height: 49, paddingHorizontal: 15, fontSize: 13, color: '#222226', backgroundColor: '#FBFBFC' },
  forgotRow: { alignItems: 'flex-end', marginTop: -4, marginBottom: 19 },
  forgotText: { fontSize: 11, color: '#606068' },
  primaryButton: { height: 48, borderRadius: 8, alignItems: 'center', justifyContent: 'center', backgroundColor: '#1C1C1E', marginTop: 3 },
  primaryButtonText: { fontSize: 13, fontWeight: '600', color: '#FFFFFF' },
  orRow: { flexDirection: 'row', alignItems: 'center', gap: 15, marginVertical: 24 },
  orLine: { height: 1, backgroundColor: '#E6E6E9', flex: 1 },
  orText: { fontSize: 11, color: '#BABAC0' },
  googleButton: { height: 47, borderRadius: 8, borderWidth: 1, borderColor: '#E4E5E8', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 12 },
  googleG: { fontSize: 19, fontWeight: '700', color: '#4285F4' },
  googleButtonText: { fontSize: 12, color: '#2A2A2E', fontWeight: '600' },
  footerSwitch: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: 28 },
  footerMuted: { fontSize: 11, color: '#A1A1A8' },
  footerLink: { fontSize: 11, fontWeight: '700', color: '#262629' },
  disclaimerWrap: { borderTopWidth: 1, borderColor: '#F2F2F3', marginTop: 34, paddingTop: 22 },
  disclaimer: { textAlign: 'center', fontSize: 10, color: '#C2C3C9', lineHeight: 17 },
});
