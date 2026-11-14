// Share one .env with the FastAPI backend (HEXCLAVE_PROJECT_ID, HEXCLAVE_PUBLISHABLE_CLIENT_KEY).
process.loadEnvFile("../.env");

export default {
  // /api/* goes to FastAPI, so the browser talks to one origin (no CORS).
  rewrites: async () => [{ source: "/api/:path*", destination: "http://localhost:8000/:path*" }],
};
