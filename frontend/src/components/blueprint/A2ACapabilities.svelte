<script>
  import { i18n } from '../../lib/i18n/index.js';

  /** @type {{ capabilities?: Object }} */
  let { capabilities = {} } = $props();

  let t = $derived((key) => $i18n[key] || key);

  let skills = $derived(capabilities.skills || []);
  let inputModes = $derived(capabilities.input_modes || []);
  let outputModes = $derived(capabilities.output_modes || []);
  let hasCapabilities = $derived(
    skills.length > 0 || inputModes.length > 0 || outputModes.length > 0
      || capabilities.name || capabilities.description
  );
  let isError = $derived(!!capabilities.error);
</script>

{#if isError}
  <div class="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
    <p class="text-sm text-red-700 dark:text-red-300">{capabilities.error}</p>
  </div>
{:else if hasCapabilities}
  <div class="p-3 bg-cyan-50 dark:bg-cyan-900/20 border border-cyan-200 dark:border-cyan-800 rounded-lg">
    <h4 class="text-sm font-semibold text-cyan-800 dark:text-cyan-200 mb-2">{t('a2a.capabilities.title')}</h4>

    {#if capabilities.name}
      <div class="mb-1">
        <span class="text-xs text-gray-500 dark:text-gray-400">Name:</span>
        <span class="text-sm text-gray-800 dark:text-gray-200">{capabilities.name}</span>
      </div>
    {/if}

    {#if capabilities.description}
      <div class="mb-1">
        <span class="text-xs text-gray-500 dark:text-gray-400">Description:</span>
        <span class="text-sm text-gray-800 dark:text-gray-200">{capabilities.description}</span>
      </div>
    {/if}

    {#if capabilities.version}
      <div class="mb-1">
        <span class="text-xs text-gray-500 dark:text-gray-400">{t('a2a.capabilities.version')}:</span>
        <span class="text-sm text-gray-800 dark:text-gray-200">{capabilities.version}</span>
      </div>
    {/if}

    {#if skills.length > 0}
      <div class="mb-1">
        <span class="text-xs text-gray-500 dark:text-gray-400">{t('a2a.capabilities.skills')}:</span>
        <ul class="mt-1 space-y-1">
          {#each skills as skill}
            <li class="text-sm text-gray-700 dark:text-gray-300">
              <strong>{skill.name || skill.id || '—'}</strong>
              {#if skill.description}
                <span class="block text-xs text-gray-500 dark:text-gray-400">{skill.description}</span>
              {/if}
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if inputModes.length > 0}
      <div class="mb-1">
        <span class="text-xs text-gray-500 dark:text-gray-400">{t('a2a.capabilities.inputModes')}:</span>
        <span class="text-sm text-gray-700 dark:text-gray-300">{inputModes.join(', ')}</span>
      </div>
    {/if}

    {#if outputModes.length > 0}
      <div class="mb-1">
        <span class="text-xs text-gray-500 dark:text-gray-400">{t('a2a.capabilities.outputModes')}:</span>
        <span class="text-sm text-gray-700 dark:text-gray-300">{outputModes.join(', ')}</span>
      </div>
    {/if}
  </div>
{/if}
