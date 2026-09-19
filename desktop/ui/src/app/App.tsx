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

import { useEffect, useRef, useState } from "react";
import { messages, type Language } from "./messages";
import { getFoundationInfo } from "../shared/ipc";
import type { FoundationInfo } from "../generated/ipc";
import logo from "../../../src-tauri/icons/brand.png";
import homeIcon from "../assets/overview.svg";
import connectionsIcon from "../assets/connections.svg";
import memoryIcon from "../assets/memory.svg";

type Page = "home" | "connections" | "memories" | "settings";
type Theme = "light" | "dark" | "system";
export function App() {
  const [language, setLanguage] = useState<Language>("zh");
  const [theme, setTheme] = useState<Theme>("system");
  const [page, setPage] = useState<Page>("home");
  const [menu, setMenu] = useState(false);
  const [host, setHost] = useState<FoundationInfo | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const t = messages[language];
  useEffect(() => {
    getFoundationInfo()
      .then(setHost)
      .catch(() => setHost(null));
  }, []);
  useEffect(() => {
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  }, [language]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  function navigate(next: Page) {
    setPage(next);
    setMenu(false);
    requestAnimationFrame(() => heading.current?.focus());
  }
  const connectButton = (
    <button className="primary" onClick={() => navigate("connections")}>
      {t.connect}
      <span aria-hidden="true"> →</span>
    </button>
  );
  return (
    <div className="app">
      <a className="skip" href="#main">
        {t.skip}
      </a>
      <header className="mobile-bar">
        <span>PowerContext</span>
        <button
          aria-expanded={menu}
          aria-controls="navigation"
          onClick={() => setMenu(!menu)}
        >
          {t.menu}
        </button>
      </header>
      <aside id="navigation" className={menu ? "sidebar open" : "sidebar"}>
        <div className="brand">
          <img src={logo} alt="" />
          <strong>PowerContext</strong>
        </div>
        <nav aria-label={t.menu}>
          {(["home", "connections", "memories"] as const).map((item, index) => (
            <button
              key={item}
              aria-current={page === item ? "page" : undefined}
              onClick={() => navigate(item)}
            >
              <img
                className="nav-symbol"
                alt=""
                src={[homeIcon, connectionsIcon, memoryIcon][index]}
              />
              {t[item]}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <p className="status">
            <span aria-hidden="true" className="dot" />
            {t.disconnected}
          </p>
          <button
            aria-current={page === "settings" ? "page" : undefined}
            onClick={() => navigate("settings")}
          >
            {t.settings}
          </button>
        </div>
      </aside>
      <main id="main">
        <div className="page-heading">
          <div>
            <h1 tabIndex={-1} ref={heading}>
              {t[page]}
            </h1>
            <p>
              {page === "home"
                ? t.tagline
                : page === "connections"
                  ? t.connectionIntro
                  : page === "memories"
                    ? t.findHint
                    : t.foundation}
            </p>
          </div>
          <span className="badge">{t.foundation}</span>
        </div>
        {page === "home" && (
          <>
            <div className="home-grid">
              <section className="card">
                <h2>{t.quick}</h2>
                <p>{t.noteHint}</p>
                <label className="sr-only" htmlFor="note">
                  {t.note}
                </label>
                <textarea
                  id="note"
                  disabled
                  aria-describedby="connection-hint"
                  placeholder={t.connectHint}
                  rows={7}
                />
                <div className="form-footer">
                  <span>{t.scope}</span>
                  <button className="primary" disabled>
                    {t.save}
                  </button>
                </div>
              </section>
              <div className="stack">
                <section className="card">
                  <h2>{t.current}</h2>
                  <p className="status">
                    <span className="dot" aria-hidden="true" />
                    {t.disconnected}
                  </p>
                  <p id="connection-hint">{t.connectHint}</p>
                  {connectButton}
                </section>
                <section className="card tip">
                  <h2>{t.tip}</h2>
                  <p>{t.tipBody}</p>
                </section>
              </div>
            </div>
            <section className="card search-card">
              <h2>{t.find}</h2>
              <p>{t.findHint}</p>
              <div className="search-row">
                <label className="sr-only" htmlFor="home-search">
                  {t.query}
                </label>
                <input id="home-search" disabled placeholder={t.query} />
                <button disabled>{t.search}</button>
              </div>
            </section>
          </>
        )}
        {page === "connections" && (
          <div className="connection-grid">
            <section className="card">
              <h2>{t.noConnections}</h2>
              <p>{t.foundationHint}</p>
            </section>
            <section className="card">
              <h2>{t.connect}</h2>
              <p>{t.connectHint}</p>
              <div className="notice">{t.foundationHint}</div>
              <details>
                <summary>{t.details}</summary>
                <dl>
                  {[t.identity, t.readiness, t.compatibility, t.tls].map(
                    (label) => (
                      <div key={label}>
                        <dt>{label}</dt>
                        <dd>{t.unverified}</dd>
                      </div>
                    ),
                  )}
                </dl>
              </details>
              <p>{t.boundary}</p>
            </section>
          </div>
        )}
        {page === "memories" && (
          <section className="card">
            <div className="search-row">
              <label className="sr-only" htmlFor="memory-search">
                {t.query}
              </label>
              <input id="memory-search" disabled placeholder={t.query} />
              <button disabled>{t.search}</button>
            </div>
            <p className="small">{t.searchLimit}</p>
            <div className="empty">
              <span className="empty-icon" aria-hidden="true">
                ▤
              </span>
              <h2>{t.empty}</h2>
              <p>{t.emptyHint}</p>
              {connectButton}
            </div>
          </section>
        )}
        {page === "settings" && (
          <div className="stack settings">
            <section className="card">
              <div className="setting-row">
                <label htmlFor="language">{t.language}</label>
                <select
                  id="language"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as Language)}
                >
                  <option value="zh">简体中文</option>
                  <option value="en">English</option>
                </select>
              </div>
              <div className="setting-row">
                <label htmlFor="theme">{t.theme}</label>
                <select
                  id="theme"
                  value={theme}
                  onChange={(e) => setTheme(e.target.value as Theme)}
                >
                  <option value="system">{t.system}</option>
                  <option value="light">{t.light}</option>
                  <option value="dark">{t.dark}</option>
                </select>
              </div>
            </section>
            <section className="card">
              <h2>{t.diagnostics}</h2>
              <p>{t.diagnosticsHint}</p>
              <dl>
                <div>
                  <dt>{t.version}</dt>
                  <dd>{host?.version ?? "0.1.0"}</dd>
                </div>
                <div>
                  <dt>{t.native}</dt>
                  <dd role="status">{host ? t.nativeReady : t.unavailable}</dd>
                </div>
              </dl>
              <p>{t.boundary}</p>
            </section>
          </div>
        )}
        <footer>{t.privacy}</footer>
      </main>
    </div>
  );
}
