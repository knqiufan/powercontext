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

// Generated from Rust IPC types. Do not edit.
export type SafeError = "unauthorized_window" | "invalid_endpoint" | "insecure_transport" | "invalid_certificate" | "credential_unavailable" | "credential_missing" | "invalid_credential" | "timeout" | "tls" | "network" | "redirect" | "unauthorized" | "forbidden" | "server" | "invalid_response" | "response_too_large" | "busy";
export type FoundationInfo = { version: string, phase: string, credentialBackend: string, serverConnected: boolean, };
export type StorageChoice = "persistent" | "session_only";
export type CredentialWriteRequest = { secret: string, storage: StorageChoice, };
export type CredentialWriteReceipt = { storage: StorageChoice, };
