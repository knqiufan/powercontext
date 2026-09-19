/*
 * Copyright (c) 2026 OceanBase.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Scopes } from "../src/app/Scopes";
import { desktopApi } from "../src/shared/ipc";
import type { DesktopState, ScopePage } from "../src/generated/ipc";
vi.mock("../src/shared/ipc", () => ({
  desktopApi: { scopes: vi.fn(), cancelScopes: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const emptyFact = { value: null, error: null };
const state: DesktopState = {
  generation: 1,
  profiles: [],
  reports: [],
  compatibilityProfiles: [],
  pendingCredentialCleanup: 0,
  active: {
    connectionId: "test",
    generation: 1,
    scope: null,
    report: {
      connectionId: "test",
      revision: 1,
      checkedAt: 1,
      liveness: emptyFact,
      readiness: emptyFact,
      identity: emptyFact,
      capabilities: emptyFact,
      compatibilityVerified: true,
      anonymousAccess: true,
      supportedOperations: ["list_scopes"],
    },
  },
};
test("editing a query cancels the native read and hides a late response", async () => {
  const user = userEvent.setup();
  let finish!: (page: ScopePage) => void;
  vi.mocked(desktopApi.scopes).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  vi.mocked(desktopApi.cancelScopes).mockResolvedValue();
  render(
    <Scopes
      state={state}
      language="en"
      onState={vi.fn()}
      confirmSwitch={() => true}
    />,
  );
  await user.click(screen.getByRole("button", { name: "Find scopes" }));
  await user.type(screen.getByLabelText("Find scopes by title"), "new");
  expect(desktopApi.cancelScopes).toHaveBeenCalledWith(1);
  await act(async () => {
    finish({
      items: [
        {
          scope_id: "old",
          title: "Old private title",
          summary: "",
          parent_scope_id: null,
          context_references: [],
          external_references: [],
          version: 1,
        },
      ],
      next_cursor: "old-page",
    });
  });
  expect(screen.queryByText("Old private title")).toBeNull();
  expect(screen.queryByRole("button", { name: "Next page" })).toBeNull();
  vi.mocked(desktopApi.scopes).mockResolvedValue({
    items: [],
    next_cursor: null,
  });
  await user.click(screen.getByRole("button", { name: "Find scopes" }));
  expect(desktopApi.scopes).toHaveBeenLastCalledWith(1, "new", null);
  expect(screen.getByText("No accessible scopes on this page.")).toBeTruthy();
});
