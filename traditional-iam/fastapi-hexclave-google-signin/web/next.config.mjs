// Share one .env with the FastAPI backend (STACKAUTH_BASE_URL, STACKAUTH_PROJECT_ID, STACKAUTH_PUBLISHABLE_CLIENT_KEY).
process.loadEnvFile("../.env");

export default {
  env: {
    NEXT_PUBLIC_HEXCLAVE_API_URL: process.env.STACKAUTH_BASE_URL,
    NEXT_PUBLIC_HEXCLAVE_PROJECT_ID: process.env.STACKAUTH_PROJECT_ID,
    NEXT_PUBLIC_HEXCLAVE_PUBLISHABLE_CLIENT_KEY: process.env.STACKAUTH_PUBLISHABLE_CLIENT_KEY,
  },
  // /api/* goes to FastAPI, so the browser talks to one origin (no CORS).
  rewrites: async () => [{ source: "/api/:path*", destination: "http://localhost:8000/:path*" }],
};
