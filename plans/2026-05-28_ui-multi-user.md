# UI-Plan: Multi-User Oberfläche

**Datum:** 2026-05-28  
**Status:** Entwurf  
**Abhängigkeiten:** Phasen 1–6 abgeschlossen (Auth, Tenants, Tasks, Deploy, Observability, Migration)  
**Ziel:** Alle neuen Multi-User-Backend-Funktionen mit passenden UI-Elementen ergänzen.

---

## Ausgangslage

| Bereich | Backend-API | Frontend-UI |
|---------|-------------|-------------|
| Login/Register | ✅ `/api/v1/auth` | ✅ `LoginView.svelte` |
| User Management (Admin) | ✅ `/api/v1/auth/users` | ✅ `UserManagement.svelte` |
| Tenant-Verwaltung | ✅ `/api/v1/tenants` (5 Endpunkte) | ❌ Keine UI |
| BYOK (API-Keys) | ✅ `/api/v1/user-keys` (4 Endpunkte) | ❌ API-Client existiert, keine UI |
| Benutzerprofil | ✅ `/api/v1/auth/me`, `/auth/password` | ❌ Keine UI |
| Server-Health | ✅ `/health` (SQLite, Redis, Auth-DB) | ⚠️ Nur Header-Indikator |
| Passwort ändern | ✅ `PUT /api/v1/auth/password` | ❌ Funktion existiert in auth.js, kein UI |
| Tenant-Quotas | ✅ Backend-Checks existieren | ❌ Keine Anzeige |

---

## Geplante UI-Elemente

### Übersicht

| # | View/Component | Route | Priorität | Aufwand |
|---|----------------|-------|-----------|---------|
| 1 | `ProfileView.svelte` | `#/profile` | Hoch | 2h |
| 2 | `TenantSettingsView.svelte` | `#/tenant-settings` | Hoch | 3h |
| 3 | `BYOKManager.svelte` | `#/my-keys` | Hoch | 2h |
| 4 | `ServerHealthView.svelte` | `#/server-health` | Mittel | 1.5h |
| 5 | Header-Updates (User-Menü) | — | Hoch | 1h |
| 6 | Sidebar-Updates (Admin + Account) | — | Hoch | 0.5h |
| 7 | App.svelte Routen | — | Hoch | 0.5h |
| 8 | i18n-Keys (en + de) | — | Hoch | 1h |
| 9 | Dashboard Quota-Anzeige | — | Niedrig | 1h |

**Gesamtaufwand:** ~12.5h

---

### 1. ProfileView.svelte (`#/profile`)

**Zweck:** Eigenes Benutzerprofil anzeigen und bearbeiten.

**Funktionen:**
- Anzeige: Name, E-Mail, Rolle, Tenant, Erstellt-Datum
- Passwort ändern (aktuelles Passwort + neues Passwort + Bestätigung)
- Optional: Anzeigenamen ändern (benötigt `PUT /api/v1/auth/me` im Backend)

**Backend-Endpunkte:**
- `GET /api/v1/auth/me` → User-Daten laden
- `PUT /api/v1/auth/password` → Passwort ändern

**Layout:**
```
┌─────────────────────────────────────┐
│ 👤 Mein Profil                      │
├─────────────────────────────────────┤
│ Name:       Max Mustermann          │
│ E-Mail:     max@example.com         │
│ Rolle:      Admin                   │
│ Tenant:     Default                 │
│ Erstellt:   28.05.2026              │
├─────────────────────────────────────┤
│ 🔒 Passwort ändern                  │
│ [Aktuelles Passwort        ]        │
│ [Neues Passwort            ]        │
│ [Neues Passwort bestätigen ]        │
│ [Passwort ändern]                   │
└─────────────────────────────────────┘
```

**i18n-Keys:** `profile.title`, `profile.name`, `profile.email`, `profile.role`, `profile.tenant`, `profile.changePassword`, `profile.currentPassword`, `profile.newPassword`, `profile.confirmPassword`, `profile.passwordChanged`, `profile.passwordMismatch`

---

### 2. TenantSettingsView.svelte (`#/tenant-settings`)

**Zweck:** Tenant-Verwaltung für Admins. Zeigt Tenant-Infos, Quotas und Benutzer.

**Funktionen:**
- Tenant-Name und Plan anzeigen
- Quotas anzeigen (max_projects, max_concurrent_debates, max_documents, max_storage_mb)
- Tenant-Benutzerliste (aus `/api/v1/tenants/current/users`)
- Benutzer einladen (E-Mail + Rolle)
- Benutzer entfernen

**Backend-Endpunkte:**
- `GET /api/v1/tenants/current` → Tenant-Daten
- `PUT /api/v1/tenants/current/settings` → Tenant-Settings ändern
- `GET /api/v1/tenants/current/users` → Benutzerliste
- `POST /api/v1/tenants/current/invite` → Benutzer einladen
- `DELETE /api/v1/tenants/current/users/{id}` → Benutzer entfernen

**Layout:**
```
┌─────────────────────────────────────┐
│ 🏢 Tenant-Einstellungen             │
├─────────────────────────────────────┤
│ Name:    Default                    │
│ Plan:    Free                       │
├─────────────────────────────────────┤
│ 📊 Quotas                           │
│ Projekte:        2 / 5              │
│ Parallele Deb.:  0 / 2              │
│ Dokumente:       12 / 50            │
│ Speicher:        45 MB / 500 MB     │
├─────────────────────────────────────┤
│ 👥 Benutzer (3)                     │
│ [admin@danwa.local] [Admin] [—]     │
│ [alice@test.com]   [Editor] [✕]     │
│ [bob@test.com]     [Viewer] [✕]     │
├─────────────────────────────────────┤
│ ➕ Benutzer einladen                │
│ [E-Mail] [Rolle ▾] [Einladen]      │
└─────────────────────────────────────┘
```

**i18n-Keys:** `tenant.title`, `tenant.name`, `tenant.plan`, `tenant.quotas`, `tenant.projects`, `tenant.debates`, `tenant.documents`, `tenant.storage`, `tenant.users`, `tenant.invite`, `tenant.inviteEmail`, `tenant.inviteRole`, `tenant.remove`, `tenant.removeConfirm`

---

### 3. BYOKManager.svelte (`#/my-keys`)

**Zweck:** Per-User API-Key-Verwaltung. Nutzer können eigene LLM-Keys hinterlegen.

**Funktionen:**
- Liste der hinterlegten Keys (Profil-ID, Label, Erstellt-Datum)
- Key hinzufügen (Profil-Auswahl + API-Key + Label)
- Key löschen
- Alle Keys löschen

**Backend-Endpunkte:**
- `GET /api/v1/user-keys` → Keys auflisten
- `PUT /api/v1/user-keys` → Key speichern/aktualisieren
- `DELETE /api/v1/user-keys/{profile_id}` → Key löschen
- `DELETE /api/v1/user-keys` → Alle Keys löschen

**Layout:**
```
┌─────────────────────────────────────┐
│ 🔑 Meine API-Keys (BYOK)           │
├─────────────────────────────────────┤
│ Ihre eigenen API-Keys haben         │
│ Vorrang vor den Server-Keys.        │
├─────────────────────────────────────┤
│ Profil           Label    Aktionen  │
│ openrouter-claude "Mein Key" [✕]    │
│ anthropic-gpt4   "Firma"   [✕]      │
├─────────────────────────────────────┤
│ ➕ Key hinzufügen                    │
│ [LLM-Profil ▾]                      │
│ [API-Key (wird verschlüsselt)]      │
│ [Label (optional)]                  │
│ [Speichern]                         │
│                                     │
│ [Alle Keys löschen]                 │
└─────────────────────────────────────┘
```

**i18n-Keys:** `byok.title`, `byok.description`, `byok.profile`, `byok.label`, `byok.addKey`, `byok.deleteKey`, `byok.deleteAll`, `byok.deleteConfirm`, `byok.noKeys`, `byok.keySaved`, `byok.apiKeyPlaceholder`

---

### 4. ServerHealthView.svelte (`#/server-health`)

**Zweck:** Detaillierte Server-Status-Anzeige für Admins.

**Funktionen:**
- Service-Status: SQLite, Redis, Auth-DB (ok/error/not_configured)
- Version anzeigen
- Optional: Aktive Debatten, Celery-Worker-Status

**Backend-Endpunkte:**
- `GET /health` → Service-Checks + Version

**Layout:**
```
┌─────────────────────────────────────┐
│ 🖥️ Server-Status                    │
├─────────────────────────────────────┤
│ Version:  1.1.0                     │
│ Status:   ✅ OK                     │
├─────────────────────────────────────┤
│ Komponente        Status            │
│ SQLite (Audit)    ✅ OK             │
│ SQLite (Auth)     ✅ OK             │
│ Redis             ⚠️ Nicht konf.    │
│ ChromaDB          ✅ OK             │
└─────────────────────────────────────┘
```

**i18n-Keys:** `server.title`, `server.version`, `server.status`, `server.ok`, `server.error`, `server.notConfigured`, `server.sqlite`, `server.redis`, `server.authDb`, `server.chromadb`

---

### 5. Header-Updates

**Aktueller Zustand:** Header zeigt User-Avatar, Name, Rolle. Dropdown hat "User Management" (admin) + "Logout".

**Änderungen:**
- "Mein Profil" Link hinzufügen (führt zu `#/profile`)
- "Meine API-Keys" Link hinzufügen (führt zu `#/my-keys`)
- "Tenant-Einstellungen" Link hinzufügen (admin only, führt zu `#/tenant-settings`)
- Tenant-Name unter dem User-Namen anzeigen
- "Server-Status" Link hinzufügen (admin only, führt zu `#/server-health`)

---

### 6. Sidebar-Updates

**Aktueller Zustand:** Sidebar hat Sektionen: RUN, BUILD, CONFIGURE, EVOLVE. Admins sehen "Users" unter CONFIGURE.

**Änderungen:**
- Neue Sektion **ADMINISTRATION** (admin only):
  - 👥 User Management (existiert bereits)
  - 🏢 Tenant Settings (neu)
  - 🖥️ Server Health (neu)
- Neue Sektion **ACCOUNT** (alle User):
  - 👤 My Profile (neu)
  - 🔑 My API Keys (neu)

---

### 7. App.svelte Routen

**Hinzuzufügen:**
```svelte
{:else if $route === 'profile'}
  <ProfileView />
{:else if $route === 'tenant-settings'}
  <TenantSettingsView />
{:else if $route === 'my-keys'}
  <BYOKManager />
{:else if $route === 'server-health'}
  <ServerHealthView />
```

---

### 8. i18n-Keys

**Neue Namespaces:** `profile.*`, `tenant.*`, `byok.*`, `server.*`

**Gesamtzahl neuer Keys:** ~50 (25 en + 25 de)

**Bestehende Keys zu ergänzen:**
- `auth.changePassword` → "Passwort ändern" / "Change Password"
- `auth.passwordChanged` → "Passwort geändert" / "Password changed"
- `nav.section.administration` → "Verwaltung" / "Administration"
- `nav.section.account` → "Konto" / "Account"
- `nav.profile` → "Mein Profil" / "My Profile"
- `nav.myKeys` → "Meine API-Keys" / "My API Keys"
- `nav.tenantSettings` → "Tenant-Einstellungen" / "Tenant Settings"
- `nav.serverHealth` → "Server-Status" / "Server Health"

---

## Implementierungs-Reihenfolge

```
Schritt 1: i18n-Keys erstellen (en.js + de.js)           — 1h
Schritt 2: ProfileView.svelte erstellen                   — 2h
Schritt 3: TenantSettingsView.svelte erstellen            — 3h
Schritt 4: BYOKManager.svelte erstellen                   — 2h
Schritt 5: ServerHealthView.svelte erstellen              — 1.5h
Schritt 6: Header.svelte + Sidebar.svelte aktualisieren   — 1.5h
Schritt 7: App.svelte Routen ergänzen                     — 0.5h
Schritt 8: Dashboard Quota-Anzeige (optional)             — 1h
Schritt 9: Tests + Lint + Commit                          — 0.5h
```

---

## Offene Backend-Fragen

| Frage | Auswirkung |
|-------|------------|
| `PUT /api/v1/auth/me` für Anzeigenamen-Änderung existiert nicht | ProfileView kann nur Passwort ändern, nicht den Namen |
| Tenant-Settings erfordern `role=admin` Prüfung | Frontend muss Admin-Status kennen (aus JWT-Token) |
| BYOK-Keys werden als Plaintext gespeichert | In Produktion sollte Verschlüsselung ergänzt werden |
| Kein `GET /api/v1/tenants/current/quotas` Endpoint | Quotas müssen aus `/tenants/current` extrahiert werden |
