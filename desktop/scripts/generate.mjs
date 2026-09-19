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

import { readFile, writeFile, mkdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import YAML from "yaml";
import openapiTS, { astToString } from "openapi-typescript";

const root = new URL("../", import.meta.url);
const contractUrl = new URL("../openapi/powercontext.yaml", root);
const raw = await readFile(contractUrl, "utf8");
const contract = YAML.parse(raw);
const wanted = [
  "get_liveness",
  "get_readiness",
  "get_capabilities",
  "get_access_principal",
  "list_scopes",
  "get_scope",
  "get_default_scope",
  "remember_memory",
  "search_memory",
  "get_memory_entry",
];
const operations = {};
for (const [path, item] of Object.entries(contract.paths)) {
  for (const [method, op] of Object.entries(item)) {
    if (wanted.includes(op?.operationId)) {
      if (operations[op.operationId]) throw new Error("Duplicate operation");
      operations[op.operationId] = { method: method.toUpperCase(), path };
    }
  }
}
if (Object.keys(operations).length !== wanted.length)
  throw new Error("Missing public operation");
const digest = createHash("sha256")
  .update(raw.replaceAll("\r\n", "\n"))
  .digest("hex");
const license =
  (await readFile(new URL(import.meta.url), "utf8")).split(" */")[0] +
  " */\n\n";
const header =
  license + "// Generated from openapi/powercontext.yaml. Do not edit.\n";
const outputs = {
  "ui/src/generated/api.d.ts": header + astToString(await openapiTS(contract)),
  "ui/src/generated/operations.ts":
    header +
    "export const contractSha256 = " +
    JSON.stringify(digest) +
    ";\nexport const operations = " +
    JSON.stringify(operations, null, 2) +
    " as const;\n",
  "src-tauri/src/transport/operations.json":
    JSON.stringify({ contractSha256: digest, operations }, null, 2) + "\n",
};
for (const [name, text] of Object.entries(outputs)) {
  const target = new URL(name, root);
  if (process.argv.includes("--check")) {
    if ((await readFile(target, "utf8")).replaceAll("\r\n", "\n") !== text)
      throw new Error("Contract drift: " + name);
  } else {
    await mkdir(fileURLToPath(new URL(".", target)), { recursive: true });
    await writeFile(target, text);
  }
}
console.log(
  process.argv.includes("--check")
    ? "Desktop contract matches OpenAPI."
    : "Desktop contract generated.",
);
