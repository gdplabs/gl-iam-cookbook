"use client";

import { SignIn, UserButton, useUser } from "@hexclave/next";
import { useEffect, useState } from "react";

export default function Home() {
  const user = useUser();
  const [me, setMe] = useState(null);

  useEffect(() => {
    if (!user) return;
    user.getAccessToken()
      .then((token) => fetch("/api/me", { headers: { Authorization: `Bearer ${token}` } }))
      .then((response) => response.json())
      .then(setMe)
      .catch((error) => setMe({ error: error.message }));
  }, [user?.id]);

  if (!user) return <SignIn />;

  return (
    <>
      <UserButton />
      <pre>GET /me {JSON.stringify(me, null, 2)}</pre>
    </>
  );
}
