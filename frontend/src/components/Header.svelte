<script>
  import { healthStatus, route } from '../lib/stores.js';
  import { tStore } from '../lib/i18n/index.js';
  import { getLLMActivity } from '../lib/api.js';
  import LanguageSwitcher from './LanguageSwitcher.svelte';
  import CaseSelector from './CaseSelector.svelte';
  import TenantSelector from './TenantSelector.svelte';
  import { currentUser } from '../lib/stores/auth.svelte.js';
  import { logout } from '../lib/auth.js';

  let { isAssistantOpen, onToggle } = $props();

  let t = $derived($tStore);

  // Map current route to a localized page title for the <h1>.
  // Falls back to a generic title when the route has no nav.<id> key.
  let pageTitle = $derived(t('nav.' + $route) || t('app.title'));

  let statusColor = $derived($healthStatus.status === 'ok'
    ? 'bg-green-500'
    : $healthStatus.status === 'unknown'
      ? 'bg-yellow-500'
      : 'bg-red-500');

  let healthIcon = $derived(
    $healthStatus.status === 'ok' ? '✅'
      : $healthStatus.status === 'unknown' ? '⏳'
        : '⚠️'
  );

  let healthLabel = $derived(
    $healthStatus.status === 'ok' ? t('health.ok')
      : $healthStatus.status === 'unknown' ? t('health.checking')
        : t('health.unreachable')
  );

  // --- LLM Activity Monitoring ---
  let llmActivity = $state({
    active_count: 0,
    active: [],
    recent: [],
    total_tokens_all_sessions: 0,
    session_totals: {},
  });

  // Token warning thresholds
  const TOKEN_WARN = 100_000;
  const TOKEN_DANGER = 500_000;
  const TOKEN_CRITICAL = 1_000_000;

  // Derived: are there active calls?
  let isActive = $derived(llmActivity.active_count > 0);

  // Derived: total tokens formatted
  let totalTokens = $derived(llmActivity.total_tokens_all_sessions);
  let tokenFormatted = $derived(
    totalTokens >= 1_000_000
      ? `${(totalTokens / 1_000_000).toFixed(1)}M`
      : totalTokens >= 1_000
        ? `${(totalTokens / 1_000).toFixed(1)}k`
        : `${totalTokens}`
  );

  // Derived: token warning level
  let tokenLevel = $derived(
    totalTokens >= TOKEN_CRITICAL ? 'critical'
      : totalTokens >= TOKEN_DANGER ? 'danger'
        : totalTokens >= TOKEN_WARN ? 'warn'
          : 'normal'
  );

  // Derived: active call summary (first active call for display)
  let primaryActive = $derived(
    llmActivity.active.length > 0 ? llmActivity.active[0] : null
  );

  // Derived: recent failed calls
  let recentFailures = $derived(
    llmActivity.recent.filter(c => c.status === 'failed').length
  );

  // Poll every 4 seconds
  $effect(() => {
    const id = setInterval(async () => {
      try {
        const data = await getLLMActivity();
        llmActivity = data;
      } catch (e) {
        if (import.meta.env.DEV) console.warn('[Header] LLM activity poll failed:', e);
      }
    }, 4000);
    return () => clearInterval(id);
  });

  // Helper: format elapsed time
  function fmtElapsed(s) {
    if (s < 60) return `${Math.round(s)}s`;
    return `${Math.floor(s / 60)}m${Math.round(s % 60)}s`;
  }

  // --- User Dropdown ---
  let userDropdownOpen = $state(false);

  function toggleUserDropdown() {
    userDropdownOpen = !userDropdownOpen;
  }

  function handleLogout() {
    logout();
    userDropdownOpen = false;
    route.set('login');
    window.location.hash = '#/login';
  }

  function goToUserManagement() {
    userDropdownOpen = false;
    window.location.hash = '#/users';
  }

  // Close dropdown on click outside
  $effect(() => {
    if (!userDropdownOpen) return;
    function onDocClick(e) {
      const el = e.target;
      if (!el.closest('.user-dropdown')) {
        userDropdownOpen = false;
      }
    }
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  });
</script>

<header class="h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-6">
  <div class="flex items-center gap-4 min-w-0">
    <h1 class="text-lg font-semibold text-gray-800 dark:text-white shrink-0">
      {pageTitle}
    </h1>

    <!-- LLM Activity Indicator -->
    {#if isActive || totalTokens > 0}
      <div class="llm-activity" class:active={isActive} class:warn={tokenLevel === 'warn'} class:danger={tokenLevel === 'danger'} class:critical={tokenLevel === 'critical'}>
        {#if isActive}
          <span class="llm-pulse"></span>
          <span class="llm-text">
            {#if primaryActive}
              {#if primaryActive.context}
                <span class="llm-context">{primaryActive.context}</span>
              {/if}
              <span class="llm-model">{primaryActive.model}</span>
              <span class="llm-elapsed">· {fmtElapsed(primaryActive.elapsed_s)}</span>
            {:else}
              Contacting LLM…
            {/if}
            {#if llmActivity.active_count > 1}
              <span class="llm-count">+{llmActivity.active_count - 1}</span>
            {/if}
          </span>
        {/if}
        {#if totalTokens > 0}
          <span class="llm-tokens" class:token-warn={tokenLevel === 'warn'} class:token-danger={tokenLevel === 'danger'} class:token-critical={tokenLevel === 'critical'}>
            {#if isActive}·{/if}
            {tokenFormatted} tok
          </span>
        {/if}
        {#if recentFailures > 0}
          <span class="llm-errors" title={t('header.recentFailures', { count: recentFailures })}>⚠{recentFailures}</span>
        {/if}
      </div>
    {/if}
  </div>

  <div class="flex items-center space-x-4">
    <!-- Tenant selector -->
    <TenantSelector />

    <!-- Case selector -->
    <CaseSelector compact={true} />

    <!-- Language switcher -->
    <LanguageSwitcher />

    <!-- Health indicator (includes version from backend). aria-live="polite"
         announces status changes to screen readers without interrupting. -->
    <div
      class="flex items-center space-x-2"
      role="status"
      aria-live="polite"
      aria-atomic="true"
      aria-label={`${t('health.label')}: ${healthLabel}`}
    >
      <span aria-hidden="true">{healthIcon}</span>
      <span class="relative flex h-3 w-3" aria-hidden="true">
        <span class="animate-ping absolute inline-flex h-full w-full rounded-full {statusColor} opacity-75"></span>
        <span class="relative inline-flex rounded-full h-3 w-3 {statusColor}"></span>
      </span>
      <span class="text-sm text-gray-600 dark:text-gray-300">
        {healthLabel}
        {#if $healthStatus.version}
          <span class="text-xs text-gray-500">({$healthStatus.version})</span>
        {/if}
      </span>
    </div>

    <!-- User Dropdown -->
    {#if $currentUser}
      <div class="relative user-dropdown">
        <button
          class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors border border-gray-200 dark:border-gray-600"
          onclick={toggleUserDropdown}
          aria-haspopup="true"
          aria-expanded={userDropdownOpen}
        >
          <span class="w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold">
            {($currentUser.display_name || $currentUser.email)[0].toUpperCase()}
          </span>
          <span class="hidden sm:inline max-w-[120px] truncate">{$currentUser.display_name || $currentUser.email}</span>
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {#if userDropdownOpen}
          <div class="absolute right-0 top-full mt-1 z-50 w-56 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1">
            <div class="px-4 py-2 border-b border-gray-100 dark:border-gray-700">
              <p class="text-sm font-medium text-gray-800 dark:text-white truncate">{$currentUser.display_name || $currentUser.email}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">{$currentUser.email}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {t('auth.role', { role: t('auth.role_' + $currentUser.role) || $currentUser.role })}
              </p>
            </div>
            {#if $currentUser.role === 'admin'}
              <button class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" onclick={goToUserManagement}>
                👥 {t('users.title')}
              </button>
            {/if}
            <button class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" onclick={() => { userDropdownOpen = false; window.location.hash = '#/profile'; }}>
              👤 {t('nav.profile')}
            </button>
            <button class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" onclick={() => { userDropdownOpen = false; window.location.hash = '#/my-keys'; }}>
              🔑 {t('nav.myKeys')}
            </button>
            {#if $currentUser.role === 'admin'}
              <button class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" onclick={() => { userDropdownOpen = false; window.location.hash = '#/tenant-settings'; }}>
                🏢 {t('nav.tenantSettings')}
              </button>
              <button class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" onclick={() => { userDropdownOpen = false; window.location.hash = '#/server-health'; }}>
                🖥️ {t('nav.serverHealth')}
              </button>
            {/if}
            <div class="border-t border-gray-100 dark:border-gray-700 my-1"></div>
            <button class="w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors" onclick={handleLogout}>
              🚪 {t('auth.logout')}
            </button>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Kitsune toggle button -->
    <button
      class="kitsune-toggle"
      class:active={isAssistantOpen}
      onclick={onToggle}
      title={t('header.kitsuneToggle')}
      aria-label={t('header.kitsuneLabel')}
    >
      <span class="kitsune-icon">🦊</span>
      <span class="kitsune-label">Kitsune</span>
    </button>
  </div>
</header>

<style>
  .kitsune-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 13px;
    color: #374151;
  }

  .kitsune-toggle:hover {
    background: #e5e7eb;
  }

  .kitsune-toggle.active {
    background: #667eea;
    color: white;
    border-color: #667eea;
  }

  :global(.dark) .kitsune-toggle {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }

  :global(.dark) .kitsune-toggle:hover {
    background: #4b5563;
  }

  :global(.dark) .kitsune-toggle.active {
    background: #667eea;
    color: white;
    border-color: #818cf8;
  }

  .kitsune-icon {
    font-size: 16px;
  }

  .kitsune-label {
    font-weight: 500;
  }

  @media (max-width: 768px) {
    .kitsune-label {
      display: none;
    }

    .kitsune-toggle {
      padding: 6px 8px;
    }
  }

  /* --- LLM Activity Indicator --- */
  .llm-activity {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    color: #166534;
    transition: all 0.3s;
    max-width: 600px;
    white-space: nowrap;
  }

  .llm-activity.active {
    background: #eff6ff;
    border-color: #bfdbfe;
    color: #1e40af;
  }

  :global(.dark) .llm-activity {
    background: #052e16;
    border-color: #166534;
    color: #86efac;
  }

  :global(.dark) .llm-activity.active {
    background: #172554;
    border-color: #1e40af;
    color: #93c5fd;
  }

  /* Warning levels */
  .llm-activity.warn {
    background: #fffbeb;
    border-color: #fde68a;
    color: #92400e;
  }

  .llm-activity.danger {
    background: #fef2f2;
    border-color: #fecaca;
    color: #991b1b;
  }

  .llm-activity.critical {
    background: #fef2f2;
    border-color: #f87171;
    color: #991b1b;
    animation: pulse-border 1.5s ease-in-out infinite;
  }

  :global(.dark) .llm-activity.warn {
    background: #451a03;
    border-color: #92400e;
    color: #fde68a;
  }

  :global(.dark) .llm-activity.danger {
    background: #450a0a;
    border-color: #991b1b;
    color: #fca5a5;
  }

  :global(.dark) .llm-activity.critical {
    background: #450a0a;
    border-color: #dc2626;
    color: #fca5a5;
    animation: pulse-border 1.5s ease-in-out infinite;
  }

  @keyframes pulse-border {
    0%, 100% { border-color: #f87171; }
    50% { border-color: #dc2626; box-shadow: 0 0 8px rgba(220, 38, 38, 0.3); }
  }

  .llm-pulse {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #3b82f6;
    animation: blink 1s ease-in-out infinite;
    flex-shrink: 0;
  }

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  .llm-text {
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
  }

  .llm-context {
    font-weight: 600;
    opacity: 0.9;
  }

  .llm-elapsed {
    font-weight: 400;
    opacity: 0.7;
  }

  .llm-count {
    font-size: 10px;
    padding: 0 4px;
    border-radius: 4px;
    background: rgba(59, 130, 246, 0.15);
    font-weight: 600;
  }

  .llm-tokens {
    font-weight: 500;
  }

  .token-warn {
    color: #b45309;
  }

  .token-danger {
    color: #dc2626;
    font-weight: 700;
  }

  .token-critical {
    color: #dc2626;
    font-weight: 700;
    text-decoration: underline wavy;
  }

  .llm-errors {
    font-size: 11px;
    color: #dc2626;
    cursor: help;
  }

  :global(.dark) .llm-pulse {
    background: #60a5fa;
  }

  :global(.dark) .token-warn {
    color: #fbbf24;
  }

  :global(.dark) .token-danger {
    color: #f87171;
  }

  :global(.dark) .token-critical {
    color: #f87171;
  }

  :global(.dark) .llm-errors {
    color: #f87171;
  }

  @media (max-width: 900px) {
    .llm-activity {
      max-width: 350px;
    }
  }

  @media (max-width: 640px) {
    .llm-activity {
      display: none;
    }
  }
</style>
