import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import OrgSettingsPage from "../pages/OrgSettingsPage";
import type { ApiToken, Me } from "../lib/types";

function buildMe(role: string): Me {
  return {
    user: {
      id: 1,
      username: "alice",
      email: "alice@example.com",
      first_name: "",
      last_name: "",
      is_staff: false,
      is_superuser: false,
    },
    organizations: [{ id: "org-1", name: "Acme", slug: "acme", role, is_active: true }],
    onboarding_complete: true,
  };
}

let me = buildMe("owner");

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ me, loading: false, refresh: vi.fn() }),
}));

const tokens: ApiToken[] = [
  {
    id: 3,
    name: "status-page",
    is_active: true,
    last_used_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
  },
];

function renderPage() {
  const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const path = String(url);
    const method = init?.method ?? "GET";
    if (path.includes("/api-tokens/") && method === "POST") {
      return Promise.resolve(
        new Response(
          JSON.stringify({ id: 4, name: "polaris", token: "pgr_secret-value", is_active: true }),
          { status: 201 },
        ),
      );
    }
    if (path.includes("/api-tokens") && method === "GET") {
      return Promise.resolve(new Response(JSON.stringify(tokens), { status: 200 }));
    }
    if (path.includes("/members") || path.includes("/invitations")) {
      return Promise.resolve(new Response("[]", { status: 200 }));
    }
    return Promise.resolve(new Response("{}", { status: 200 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
  document.cookie = "csrftoken=test-token; path=/";
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <OrgSettingsPage />
    </QueryClientProvider>,
  );
  return fetchMock;
}

afterEach(() => {
  me = buildMe("owner");
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("OrgSettingsPage API tokens", () => {
  it("lists existing tokens with their last use", async () => {
    renderPage();
    expect(await screen.findByText("status-page")).toBeInTheDocument();
    expect(screen.getByText(/last used/i)).toBeInTheDocument();
  });

  it("creates a token and shows the plaintext once", async () => {
    const fetchMock = renderPage();
    await userEvent.type(screen.getByPlaceholderText(/what will use this token/i), "polaris");
    await userEvent.click(screen.getByRole("button", { name: /create token/i }));

    expect(await screen.findByText("pgr_secret-value")).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "POST");
    expect(JSON.parse((post![1] as RequestInit).body as string)).toEqual({ name: "polaris" });

    // Dismissing clears it — the plaintext is not recoverable from the list.
    await userEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    await waitFor(() => expect(screen.queryByText("pgr_secret-value")).not.toBeInTheDocument());
  });

  it("revokes a token after confirmation", async () => {
    const fetchMock = renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /revoke/i }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([, init]) => (init as RequestInit)?.method === "DELETE",
      );
      expect(String(call![0])).toBe("/api/v1/orgs/org-1/api-tokens/3/");
    });
  });

  it("hides the section from non-owners", async () => {
    me = buildMe("member");
    renderPage();
    await waitFor(() => expect(screen.getByText(/only owners can make changes/i)).toBeVisible());
    expect(screen.queryByText(/api tokens/i)).not.toBeInTheDocument();
  });
});
