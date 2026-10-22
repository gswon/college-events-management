# NYU Event Calendar - Home screen

React Native + Expo + TypeScript implementation based ONLY on the first two Home frames in aye.pdf. No Calendar/Profile design was implemented. There was no existing team repository supplied, so this is a standalone project you can copy into the shared repository.

## Run on your Mac

Install Node.js 20.19 or newer. Unzip this project, open its folder in VS Code, then run:

```bash
npm install
npx expo install --fix
npm run typecheck
npx expo start
```

Open Expo Go on your phone and scan the QR code. Keep your Mac and phone on the same Wi-Fi. If your Expo Go version requires a newer SDK, use the official Expo SDK upgrade instructions or run this SDK in an iOS simulator/development build.

## What is included

- The two-line greeting, black JC avatar, uppercase section label, date column, three sample event rows and fixed bottom bar.
- Native status bar and safe-area spacing; scrollable content and wrapping event titles.
- Home stays selected. Other tabs explain that their screens are pending, because only Home was authorized.
- Reusable EventItem and BottomTabBar components.
- Typed API helper for GET /api/v1/users/me and GET /api/v1/events, with required start/end and cursor pagination.

## Design fidelity

The PDF is a visual reference, not an inspectable Figma component file. Sizes/colors are measured approximations; exact font tokens and exported icons were not supplied. Native system font and Feather outline icons approximate the design. The screen has no fake device frame/status bar.

Demo mode deliberately uses Wednesday, Sep 30, Joanna/JC, and the exact three events from the design. The design labels say THU OCT 2 and MON OCT 6 even though those dates are Friday and Tuesday in 2026. Those labels are preserved ONLY in demo data. Real data uses correct New York dates and daylight-saving-aware times.

## Backend

The Home screen loads the first page (20 events) of GET /api/v1/events for the next 14 days. Copy .env.example to .env and set EXPO_PUBLIC_API_URL to the backend origin (without /api/v1). On a physical phone use your Mac's LAN IP, not localhost, and start the backend with `--host 0.0.0.0`. Restart `npx expo start` after changing .env.

The user name/avatar is still demo data: the backend has no /users/me or authentication yet. Event details and the other tabs remain team integration work. Never put passwords or access tokens in committed files.
