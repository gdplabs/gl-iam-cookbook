"use client";

import { UserButton, useUser } from "@hexclave/next";
import { useEffect, useState } from "react";

export default function Home() {
  const user = useUser({ or: "redirect" }); // signed out -> /sign-in
  const [me, setMe] = useState(null);

  useEffect(() => {
    // Call FastAPI with the Hexclave access token. GL-IAM checks it there.
    user.getAccessToken()
      .then((token) => fetch("/api/me", { headers: { Authorization: `Bearer ${token}` } }))
      .then((response) => response.json())
      .then(setMe)
      .catch((error) => setMe({ error: error.message }));
  }, [user.id]);

  return (
    <>
      <UserButton />
      <pre>GET /me {JSON.stringify(me, null, 2)}</pre>
    </>
  );
}
