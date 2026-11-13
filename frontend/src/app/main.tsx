import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router/dom";

import "../i18n";
import "../styles/global.css";
import i18n from "../i18n";
import { router } from "./router";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
});

function SkipLink() {
  return (
    <a href="#main" className="skip-link">
      {i18n.t("app.skipToContent")}
    </a>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SkipLink />
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
