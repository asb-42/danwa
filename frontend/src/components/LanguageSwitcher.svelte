<script>
  import { locale, i18n } from '../lib/i18n/index.js';
  import { SUPPORTED_LOCALES, LOCALE_NAMES } from '../lib/i18n/config.js';
  import { setLanguage } from '../lib/api.js';

  let persisting = $state(false);

  async function switchLanguage(lang) {
    await i18n.setLocale(lang);
    localStorage.setItem('locale', lang);
    // Persist to backend
    persisting = true;
    try {
      await setLanguage(lang);
    } catch {
      // Non-critical — language is already set locally
    } finally {
      persisting = false;
    }
  }
</script>

<div class="flex gap-2" role="group" aria-label="Language selection">
  {#each SUPPORTED_LOCALES as lang}
    <button
      onclick={() => switchLanguage(lang)}
      class="px-3 py-1 text-sm rounded transition-colors
             {$locale === lang
               ? 'bg-blue-600 text-white'
               : 'bg-gray-200 text-gray-700 hover:bg-gray-300 dark:bg-gray-600 dark:text-gray-200 dark:hover:bg-gray-500'}"
      aria-pressed={$locale === lang}
      aria-label={LOCALE_NAMES[lang]}
    >
      {lang.toUpperCase()}
    </button>
  {/each}
</div>
