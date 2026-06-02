<script>
  import { tStore } from '../../lib/i18n/index.js';

  let {
    variants = [],
    selectedVariantId = '',
    previewContent = null,
    previewRole = 'strategist',
    previewVariantId = null,
    onCreate = () => {},
    onDelete = () => {},
    onPreview = () => {},
    onTranslate = () => {},
    onSelect = () => {},
  } = $props();

  let t = $derived($tStore);

  const PROMPT_ROLES = [
    { value: 'strategist', label: 'Strategist', emoji: '🧠' },
    { value: 'critic', label: 'Critic', emoji: '🔍' },
    { value: 'optimizer', label: 'Optimizer', emoji: '⚡' },
    { value: 'moderator', label: 'Moderator', emoji: '🎯' },
  ];
</script>

<div class="space-y-4">
  <div class="flex justify-end">
    <button class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors" onclick={onCreate}>
      + {t('config.createPromptVariant') || 'Create Prompt Variant'}
    </button>
  </div>
  {#each variants as variant}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-4">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <h4 class="text-md font-semibold text-gray-800 dark:text-white">{variant.name || variant.id}</h4>
          {#if selectedVariantId === variant.id}
            <span class="text-xs px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full">✓ {t('config.active')}</span>
          {/if}
        </div>
        <div class="flex items-center gap-2">
          <button class="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-200 dark:hover:bg-blue-800/40 transition-colors" onclick={() => onSelect(variant.id)}>
            {selectedVariantId === variant.id ? t('config.active') : t('config.select') || 'Select'}
          </button>
          <button class="text-xs px-2 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded hover:bg-purple-200 dark:hover:bg-purple-800/40 transition-colors" onclick={() => onTranslate(variant.id)} title={t('config.translatePrompt') || 'Translate'}>
            🌐 {t('config.translate') || 'Translate'}
          </button>
          {#if variant.id !== 'default'}
            <button class="text-xs px-2 py-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors" onclick={() => onDelete(variant.id, variant.id)}>
              {t('common.delete')}
            </button>
          {/if}
        </div>
      </div>
      {#if variant.description}
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">{variant.description}</p>
      {/if}
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {#each PROMPT_ROLES as role}
          <div class="p-3 rounded-lg border border-gray-200 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 transition-colors">
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm font-medium text-gray-800 dark:text-white capitalize">{role.emoji} {role.label}</span>
              <button class="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={() => onPreview(variant.id, role.value)}>
                {t('config.preview')}
              </button>
            </div>
            {#if previewContent && previewVariantId === variant.id && previewRole === role.value}
              <pre class="text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 p-2 rounded overflow-x-auto max-h-32 whitespace-pre-wrap">{previewContent}</pre>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {:else}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
      <div class="flex items-center justify-center h-32">
        <p class="text-gray-500 dark:text-gray-400">{t('config.promptVariantsPlaceholder')}</p>
      </div>
    </div>
  {/each}
</div>
