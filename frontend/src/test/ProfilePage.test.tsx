import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ProfilePage from "../pages/ProfilePage";
import * as push from "../lib/push";
import type { Me } from "../lib/types";

vi.mock("../lib/push");

const me: Me = {
  user: {
    id: 1,
    username: "alice",
    email: "alice@example.com",
    first_name: "Alice",
    last_name: "Anderson",
    is_staff: false,
    is_superuser: false,
  },
  organizations: [
    { id: "org-1", name: "Acme", slug: "acme", role: "owner", is_active: true },
  ],
  onboarding_complete: true,
};

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ me, loading: false }),
}));

const stats = {
  days: 30,
  total: 5,
  by_day: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.UTC(2026, 5, 14 + i)).toISOString().slice(0, 10),
    count: i === 29 ? 5 : 0,
  })),
};

function renderPage() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (String(url).startsWith("/api/v1/push/stats")) {
        return Promise.resolve(new Response(JSON.stringify(stats), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("ProfilePage", () => {
  it("shows the account details", async () => {
    vi.mocked(push.isPushSupported).mockReturnValue(false);
    renderPage();
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
  });

  it("explains how to get push when the browser does not support it", async () => {
    vi.mocked(push.isPushSupported).mockReturnValue(false);
    renderPage();
    expect(await screen.findByText(/not available in this browser/i)).toBeInTheDocument();
    expect(screen.getByText(/add pulsegrid to your home screen/i)).toBeInTheDocument();
  });

  it("enables push notifications end-to-end", async () => {
    vi.mocked(push.isPushSupported).mockReturnValue(true);
    vi.mocked(push.getCurrentSubscription).mockResolvedValue(null);
    vi.mocked(push.getVapidPublicKey).mockResolvedValue("server-key");
    vi.mocked(push.subscribeToPush).mockResolvedValue();

    renderPage();
    const enable = await screen.findByRole("button", { name: /enable push notifications/i });
    await userEvent.click(enable);

    await waitFor(() => expect(push.subscribeToPush).toHaveBeenCalledWith("server-key"));
    expect(await screen.findByText(/enabled on this device/i)).toBeInTheDocument();
  });

  it("offers disable and test actions when already subscribed", async () => {
    vi.mocked(push.isPushSupported).mockReturnValue(true);
    vi.mocked(push.getVapidPublicKey).mockResolvedValue("server-key");
    vi.mocked(push.getCurrentSubscription).mockResolvedValue({} as PushSubscription);

    renderPage();
    expect(await screen.findByRole("button", { name: /disable/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send test notification/i })).toBeInTheDocument();
  });

  it("shows the 30-day alert statistics", async () => {
    vi.mocked(push.isPushSupported).mockReturnValue(false);
    renderPage();
    expect(await screen.findByText(/alerts received/i)).toBeInTheDocument();
    expect(await screen.findByText(/5 alerts in the last 30 days/i)).toBeInTheDocument();
  });
});
