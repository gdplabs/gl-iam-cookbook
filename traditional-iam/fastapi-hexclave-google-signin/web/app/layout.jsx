import { HexclaveClientApp, HexclaveProvider, HexclaveTheme } from "@hexclave/next";

// Reads HEXCLAVE_PROJECT_ID and HEXCLAVE_PUBLISHABLE_CLIENT_KEY from ../.env.
const hexclave = new HexclaveClientApp({
  tokenStore: "nextjs-cookie",
  urls: { default: { type: "hosted" }, signIn: "/sign-in" },
});

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <HexclaveProvider app={hexclave}>
          <HexclaveTheme>{children}</HexclaveTheme>
        </HexclaveProvider>
      </body>
    </html>
  );
}
