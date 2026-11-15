import { HexclaveClientApp, HexclaveProvider, HexclaveTheme } from "@hexclave/next";
import { Suspense } from "react";

const hexclave = new HexclaveClientApp({
  tokenStore: "nextjs-cookie",
  urls: { default: { type: "hosted" } },
});

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <HexclaveProvider app={hexclave}>
          <HexclaveTheme>
            {/* Shown while Hexclave loads the user. */}
            <Suspense fallback="Loading...">{children}</Suspense>
          </HexclaveTheme>
        </HexclaveProvider>
      </body>
    </html>
  );
}
