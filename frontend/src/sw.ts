/// <reference lib="webworker" />
declare const self: ServiceWorkerGlobalScope;

import { precacheAndRoute } from "workbox-precaching";

// Injected by vite-plugin-pwa (injectManifest strategy).
precacheAndRoute(self.__WB_MANIFEST);

self.addEventListener("install", () => {
  void self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

interface AlertPushPayload {
  title?: string;
  body?: string;
  url?: string;
  alert?: { id?: number; kind?: string };
}

self.addEventListener("push", (event) => {
  const data: AlertPushPayload = event.data?.json() ?? {};
  event.waitUntil(
    self.registration.showNotification(data.title ?? "PulseGrid", {
      body: data.body ?? "",
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      // Re-notify (don't silently coalesce) when the same alert changes state.
      tag: data.alert?.id ? `pulsegrid-alert-${data.alert.id}-${data.alert.kind ?? ""}` : undefined,
      data: { url: data.url ?? "/alerts" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target: string = event.notification.data?.url ?? "/alerts";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      const existing = windows.find((w) => w.url.includes(target) && "focus" in w);
      if (existing) return existing.focus();
      return self.clients.openWindow(target);
    }),
  );
});
