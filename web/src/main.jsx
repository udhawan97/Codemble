// Self-hosted so the galaxy renders identically offline. The docs site pulls
// these faces from the Google Fonts CDN; the app must not — it runs locally and
// says so in its own footer.
import "@fontsource/zen-kaku-gothic-new/latin-400.css";
import "@fontsource/shippori-mincho/latin-500.css";
import "@fontsource/shippori-mincho/latin-700.css";
import "@fontsource/jetbrains-mono/latin-400.css";
import "@fontsource/jetbrains-mono/latin-500.css";

import { Component, StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App.jsx";
import "./styles.css";

class AppErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { message: "" };
  }

  static getDerivedStateFromError(error) {
    return { message: error instanceof Error ? error.message : String(error) };
  }

  componentDidCatch(error) {
    console.error("Codemble stopped rendering:", error);
  }

  render() {
    if (!this.state.message) return this.props.children;
    return (
      <main className="load-state" role="alert">
        <h1>The galaxy stopped rendering.</h1>
        <p>{this.state.message}</p>
        <p>Your progress is saved on this machine; reloading re-reads it.</p>
        <button
          className="check-primary"
          type="button"
          onClick={() => window.location.reload()}
        >
          Reload Codemble
        </button>
      </main>
    );
  }
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AppErrorBoundary>
      <App />
    </AppErrorBoundary>
  </StrictMode>,
);
