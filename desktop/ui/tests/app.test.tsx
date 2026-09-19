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

import { afterEach, expect, test } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../src/app/App";
afterEach(cleanup);
test("disconnected shell prevents writes and search and explains the boundary", async () => {
  const user = userEvent.setup();
  render(<App />);
  expect(
    (screen.getByRole("button", { name: "保存记忆" }) as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  expect(
    (screen.getByRole("button", { name: "查找" }) as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  await user.click(screen.getByRole("button", { name: /连接已有服务/ }));
  expect(screen.getByText("尚未添加连接")).toBeTruthy();
  await user.click(screen.getByText("连接状态详情"));
  expect(screen.getAllByText("未验证")).toHaveLength(4);
  expect(screen.getByText(/关闭窗口将退出桌面/)).toBeTruthy();
});
test("navigation, bilingual settings and theme remain usable without the native host", async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole("button", { name: "设置" }));
  await user.selectOptions(screen.getByLabelText("语言"), "en");
  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
    "Settings",
  );
  await user.selectOptions(screen.getByLabelText("Theme"), "dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(document.documentElement.lang).toBe("en");
  await user.click(screen.getByRole("button", { name: /My memories/ }));
  expect(
    screen.getByRole("heading", { name: "No memories to display" }),
  ).toBeTruthy();
  expect(screen.queryByRole("list")).toBeNull();
});
