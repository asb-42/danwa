<script>
  import { locale, i18n } from '../lib/i18n/index.js';
  import { SUPPORTED_LOCALES, LOCALE_NAMES, RTL_LOCALES } from '../lib/i18n/config.js';
  import { setLanguage } from '../lib/api.js';

  let open = $state(false);
  let persisting = $state(false);

  // ISO 639-1 → Flag emoji mapping
  const FLAGS = {
    de: '🇩🇪', en: '🇬🇧', fr: '🇫🇷', es: '🇪🇸', it: '🇮🇹',
    pt: '🇧🇷', ru: '🇷🇺', zh: '🇨🇳', ja: '🇯🇵', ko: '🇰🇷',
    sv: '🇸🇪', el: '🇬🇷', ar: '🇸🇦', he: '🇮🇱',
  };

  async function switchLanguage(lang) {
    await i18n.setLocale(lang);
    // Persist to backend (non-critical)
    persisting = true;
    try { await setLanguage(lang); } catch {}
    finally { persisting = false; }
    open = false;
  }

  $: currentFlag = FLAGS[$locale] || '🌐';
  $: isRTL = RTL_LOCALES.has($locale);
</script>

<div class="relative inline-block text-left">
  <button
    onclick={() => open = !open}
    class="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg
           bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600
           border border-gray-300 dark:border-gray-600
           transition-colors"
    aria-label="Sprache wechseln"
    aria-expanded={open}
  >
    <span class="text-lg leading-none">{currentFlag}</span>
    <span class="hidden sm:inline">{$locale.toUpperCase()}</span>
    <svg class="w-3 h-3 ml-1 transition-transform {open ? 'rotate-180' : ''}"
         xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
         stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
    </svg>
    {#if persisting}
      <span class="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin ml-1"></span>
    {/if}
  </button>

  {#if open}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div class="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-800 rounded-lg shadow-lg
                border border-gray-200 dark:border-gray-700 z-50
                ring-1 ring-black ring-opacity-5"
         onclick={(e) => e.stopPropagation()}>
      <div class="py-1" role="menu">
        {#each SUPPORTED_LOCALES as lang}
          {@const isRTL = RTL_LOCALES.has(lang)}
          {@const dir = isRTL ? 'rtl' : 'ltr'}
          <button
            onclick={() => switchLanguage(lang)}
            class="w-full text-left px-4 py-2 text-sm flex items-center gap-2
                   hover:bg-blue-50 dark:hover:bg-gray-700/50 transition-colors
                   {$locale === lang
                     ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                     : 'text-gray-700 dark:text-gray-300'}"
            class:font-serif={isRTL}
          >
            <span class="text-lg leading-none">{FLAGS[lang] || '🌐'}</span>
            <span dir={dir}>{LOCALE_NAMES[lang] || lang}</span>
            {#if isRTL}
              <span class="ml-auto text-xs text-gray-400 dark:text-gray-500" dir="ltr">RTL</span>
            {/if}
            {#if lang === $locale}
              <svg class="ml-auto w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24"
                   stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
              </svg>
            {/if}
          </button>
        {/each}
      </div>
    </div>
  {/if}
</div>

<!-- Close dropdown on outside click -->
{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="fixed inset-0 z-40" onclick={() => open = false}></div>
{/if}
