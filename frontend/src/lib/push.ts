import { api } from "./api";

/** Decodes a URL-safe base64 string (the VAPID public key format) into the
 * byte array the Push API expects as applicationServerKey. */
export function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((char) => char.charCodeAt(0)));
}

export function isPushSupported(): boolean {
  return typeof window !== "undefined" && "PushManager" in window && "serviceWorker" in navigator;
}

/** True when running as an installed PWA (home screen / dock) rather than a
 * browser tab — iOS only allows web push in this mode. */
export function isStandalone(): boolean {
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    // iOS Safari's non-standard flag.
    (navigator as { standalone?: boolean }).standalone === true
  );
}

export async function getVapidPublicKey(): Promise<string> {
  const { public_key } = await api<{ public_key: string }>("/api/v1/push/vapid-public-key");
  return public_key;
}

export async function getCurrentSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null;
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

/** Full registration flow: notification permission → browser subscription →
 * backend registration. Throws with a readable message on every failure mode. */
export async function subscribeToPush(vapidPublicKey: string): Promise<void> {
  if (!vapidPublicKey) {
    throw new Error("Push notifications are not configured on this server.");
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Notification permission was not granted.");
  }
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
  });
  const json = subscription.toJSON();
  await api("/api/v1/push/subscriptions", {
    method: "POST",
    body: {
      endpoint: json.endpoint,
      p256dh: json.keys?.p256dh,
      auth: json.keys?.auth,
    },
  });
}

export async function unsubscribeFromPush(): Promise<void> {
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;
  await api("/api/v1/push/subscriptions", {
    method: "DELETE",
    body: { endpoint: subscription.endpoint },
  });
  await subscription.unsubscribe();
}
