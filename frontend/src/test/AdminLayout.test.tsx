import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import AdminLayout from "../pages/admin/AdminLayout";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<p>overview content</p>} />
          <Route path="workers" element={<p>workers content</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("AdminLayout", () => {
  it("renders every admin tab", () => {
    renderAt("/admin");
    for (const tab of ["Overview", "Workers", "Regions", "Organizations", "Users", "Audit log"]) {
      expect(screen.getByRole("link", { name: tab })).toBeInTheDocument();
    }
  });

  it("renders the nested route content", () => {
    renderAt("/admin/workers");
    expect(screen.getByText("workers content")).toBeInTheDocument();
  });
});
