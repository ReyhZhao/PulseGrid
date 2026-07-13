import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChannelsPage from "../pages/ChannelsPage";
import type { Me } from "../lib/types";

const me: Me = {
  user: {
    id: 1,
    username: "alice",
    email: "alice@example.com",
    first_name: "",
    last_name: "",
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

const members = [
  { id: 1, username: "alice", email: "alice@example.com", first_name: "", last_name: "", role: "owner", created_at: "" },
  { id: 2, username: "bob", email: "bob@example.com", first_name: "Bob", last_name: "Berg", role: "member", created_at: "" },
];

const channels = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 7,
      organization: "org-1",
      name: "Ops push",
      channel_type: "push",
      config: { user_ids: [1, 2] },
      is_active: true,
    },
  ],
};

function renderPage() {
  const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const path = String(url);
    if (path.startsWith("/api/v1/channels/") && (init?.method ?? "GET") === "GET") {
      return Promise.resolve(new Response(JSON.stringify(channels), { status: 200 }));
    }
    if (path.includes("/members")) {
      return Promise.resolve(new Response(JSON.stringify(members), { status: 200 }));
    }
    if (path.startsWith("/api/v1/channels/") && init?.method === "POST") {
      return Promise.resolve(new Response(JSON.stringify({ id: 8 }), { status: 201 }));
    }
    return Promise.resolve(new Response("{}", { status: 200 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  document.cookie = "csrftoken=test-token; path=/";
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ChannelsPage />
    </QueryClientProvider>,
  );
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("ChannelsPage push channels", () => {
  it("shows org members to pick when the push type is selected", async () => {
    renderPage();
    await userEvent.selectOptions(screen.getByRole("combobox"), "push");
    expect(await screen.findByText("bob@example.com")).toBeInTheDocument();
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
  });

  it("creates a push channel with the selected members", async () => {
    const fetchMock = renderPage();
    await userEvent.selectOptions(screen.getByRole("combobox"), "push");
    await userEvent.type(screen.getByPlaceholderText("Channel name"), "Night shift");
    await userEvent.click(await screen.findByRole("checkbox", { name: /bob/i }));
    await userEvent.click(screen.getByRole("button", { name: /add channel/i }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "POST");
      expect(post).toBeTruthy();
      const body = JSON.parse((post![1] as RequestInit).body as string);
      expect(body.channel_type).toBe("push");
      expect(body.config).toEqual({ user_ids: [2] });
      expect(body.name).toBe("Night shift");
    });
  });

  it("lists push channels with their recipient count", async () => {
    renderPage();
    expect(await screen.findByText("Ops push")).toBeInTheDocument();
    expect(await screen.findByText(/2 recipients/i)).toBeInTheDocument();
  });
});
