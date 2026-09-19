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

use powercontext_desktop::{
    credentials::{CredentialWriteReceipt, CredentialWriteRequest, StorageChoice},
    error::SafeError,
    ipc::FoundationInfo,
};
use ts_rs::TS;
fn main() {
    let config = ts_rs::Config::default();
    let license = include_str!("export_ipc.rs")
        .split(" */")
        .next()
        .unwrap()
        .to_owned()
        + " */\n\n";
    let output = license
        + &format!(
            "// Generated from Rust IPC types. Do not edit.\nexport {}\nexport {}\nexport {}\nexport {}\nexport {}\n",
            SafeError::decl(&config),
            FoundationInfo::decl(&config),
            StorageChoice::decl(&config),
            CredentialWriteRequest::decl(&config),
            CredentialWriteReceipt::decl(&config)
        );
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../ui/src/generated/ipc.ts");
    if std::env::args().any(|arg| arg == "--check") {
        assert_eq!(
            std::fs::read_to_string(path).unwrap().replace("\r\n", "\n"),
            output,
            "IPC drift: run cargo run --example export_ipc"
        );
    } else {
        std::fs::write(path, output).unwrap();
    }
}
