// Self-hosted so the galaxy renders identically offline. The docs site pulls
// these faces from the Google Fonts CDN; the app must not — it runs locally and
// says so in its own footer.
import "@fontsource/zen-kaku-gothic-new/latin-400.css";
import "@fontsource/shippori-mincho/latin-500.css";
import "@fontsource/shippori-mincho/latin-700.css";
import "@fontsource/jetbrains-mono/latin-400.css";
import "@fontsource/jetbrains-mono/latin-500.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
