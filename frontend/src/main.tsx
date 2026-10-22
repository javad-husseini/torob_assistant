import { createRoot } from "react-dom/client";
import { setNonce } from "get-nonce";
import "./index.css";
import App from "./App";
const nonce = document.querySelector<HTMLMetaElement>(
  'meta[name="csp-nonce"]',
)?.content;
if (nonce && nonce !== "__CSP_NONCE__") setNonce(nonce);
createRoot(document.getElementById("root")!).render(<App />);
