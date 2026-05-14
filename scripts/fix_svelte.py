"""Fix TranslationDashboard.svelte structure"""

with open("frontend/src/views/TranslationDashboard.svelte") as f:
    content = f.read()

# The broken section spans from {#if activeTab === 'modules'} to the start of the batch tab content
# We need to replace the entire tab section (modules tab + batch tab + single module dialog)

# Find the batch tab title marker
batch_title = "<!-- Batch Translate Tab -->"
single_title = "<!-- Single Module Translate Dialog -->"

# Find boundaries
batch_idx = content.index(batch_title)
single_idx = content.index(single_title)

# The modules tab section starts at {#if activeTab === 'modules'}
modules_start = content.index("{#if activeTab === 'modules'}")

# Find the line before {#if activeTab === 'modules'}
before = content[:modules_start]

# The rest after batch tab title needs to be preserved as-is
# but we need to find properly where the batch tab content starts
after_marker = content[batch_idx:]

# The broken part is everything from modules_start to single_idx
# We'll replace just the module block structure

# Clean replacement for the entire tab structure
new_tabs = """  {#if activeTab === 'modules'}
    {#if loadingModules && languages.length === 0}
      <div class="flex items-center justify-center h-32">
        <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
      </div>
    {:else if modules.length === 0}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700 text-center">
        <p class="text-gray-500 dark:text-gray-400">{t('translation.noModules')}</p>
      </div>
    {:else}
      <!-- Language Selector -->
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-4 mb-4">
        <div class="flex items-center gap-4">
          <label class="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
            {t('translation.targetLanguage')}
          </label>
          <div class="flex-1 grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
            {#each languages as lang}
              <button
                class="px-3 py-2 rounded-lg text-sm font-medium transition-colors
                  {selectedTargetLang === lang
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'}"
                onclick={() => { selectedTargetLang = lang; }}
              >
                {lang.toUpperCase()}
              </button>
            {/each}
          </div>
        </div>
      </div>

      <!-- Module List -->
      <div class="space-y-4">
        {#each modules as module (module.id)}
          <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
            <!-- Module Header -->
            <div
              class="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
              onclick={() => handleSelectModule(module.id)}
            >
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-blue-100
                   dark:bg-blue-900/30 flex items-center justify-center
                   text-blue-600 dark:text-blue-400 font-bold text-sm">
                  {module.id.charAt(0).toUpperCase()}
                </div>
                <div>
                  <h3 class="text-sm font-semibold text-gray-800 dark:text-white">{module.id}</h3>
                  <p class="text-xs text-gray-500 dark:text-gray-400">v{module.version || '0.0.0'} · {module.manifest?.name || ''}</p>
                </div>
              </div>
              <div class="flex items-center gap-2">
                {#if $translationStatistics[module.id]}
                  {@const stats = $translationStatistics[module.id]}
                  <span class="text-xs px-2 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
                    {stats.approved || 0}/{stats.total || 0} {t('translation.approved')}
                  </span>
                {/if}
                <button
                  class="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors disabled:opacity-50"
                  disabled={singleInProgress}
                  onclick={(e) => { e.stopPropagation(); singleModuleId = module.id; singleTranslateOpen = true; }}
                >
                  {singleInProgress && singleModuleId === module.id ? t('translation.translating') : t('translation.translate')}
                </button>
              </div>
            </div>

            <!-- Translation Details (collapsible) -->
            {#if $selectedModuleId === module.id}
              <div class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
                {#if $translationResults[module.id]}
                  {@const files = $translationResults[module.id]}
                  {#if files.length === 0}
                    <p class="text-sm text-gray-500 dark:text-gray-400 py-2">{t('translation.noTranslations')}</p>
                  {:else}
                    <div class="space-y-2">
                      {#each files as file (file.file_path)}
                        <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                          <div class="flex-1 min-w-0 mr-3">
                            <p class="text-sm font-medium text-gray-800 dark:text-white truncate">{file.file_path}</p>
                            <div class="flex items-center gap-2 mt-1">
                              {#if file.quality_score != null}
                                <span class={`text-xs font-medium ${qualityColor(file.quality_score)}`}>
                                  {t('translation.quality')}: {(file.quality_score * 100).toFixed(0)}%
                                </span>
                              {/if}
                              {#if file.approved !== undefined}
                                <span class="text-xs px-1.5 py-0.5 rounded-full text-xs
                                  {file.approved
                                    ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                                    : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'}">
                                  {file.approved ? t('translation.approved') : t('translation.pending')}
                                </span>
                              {/if}
                            </div>
                            {#if file.quality_score != null}
                              <div class="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-1.5 mt-1">
                                <div
                                   class="h-1.5 rounded-full transition-all duration-500
                                     {qualityBarWidth(file.quality_score) === '0%' ? '' : 'bg-blue-600 dark:bg-blue-400'}"
                                  style="width: {qualityBarWidth(file.quality_score)}"
                                  role="progressbar"
                                  aria-valuenow={Math.round(file.quality_score * 100)}
                                  aria-valuemin="0"
                                  aria-valuemax="100"
                                ></div>
                              </div>
                            {/if}
                          </div>
                          <div class="flex gap-1 flex-shrink-0">
                            <button
                              class="p-1.5 text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 rounded transition-colors"
                              title={file.approved ? t('translation.reject') : t('translation.approve')}
                              onclick={() => handleApprove(module.id, file.file_path, !file.approved)}
                            >
                              {file.approved ? '✅' : '⏳'}
                            </button>
                            <button
                              class="p-1.5 text-gray-500 hover:text-red-600 dark:hover:text-red-400 rounded transition-colors"
                              title={t('translation.invalidate')}
                              onclick={() => handleInvalidate(module.id, file.file_path)}
                            >
                              🗑️
                            </button>
                          </div>
                        </div>
                      {/each}
                    </div>
                  {/if}
                {:else}
                  <div class="flex items-center justify-center py-8">
                    <button
                      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                      onclick={() => handleTranslateModule()}
                      disabled={singleInProgress}
                    >
                      {singleInProgress ? t('translation.translating') : t('translation.translateModule')}
                    </button>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  {:else if activeTab === 'batch'}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-6">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">
        {t('translation.batchTranslate')}
      </h3>

      <!-- Target Language -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {t('translation.targetLanguage')}
        </label>
        <div class="flex flex-wrap gap-2">
          {#each languages as lang}
            <button
              class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors
                {selectedTargetLang === lang
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'}"
              onclick={() => { selectedTargetLang = lang; }}
            >
              {lang.toUpperCase()}
            </button>
          {/each}
        </div>
      </div>

      <!-- Module Selection -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {t('translation.selectModules')}
        </label>
        {#if modules.length === 0}
          <p class="text-sm text-gray-500 dark:text-gray-400">{t('translation.noModules')}</p>
        {:else}
           <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3
                 lg:grid-cols-4 gap-2 max-h-60 overflow-y-auto p-2
                 bg-gray-50 dark:bg-gray-700 rounded-lg">
            {#each modules as module (module.id)}
              <label class="flex items-center gap-2 p-2 rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors">
                <input
                  type="checkbox"
                  checked={selectedForBatch.includes(module.id)}
                  onchange={() => {
                    if (selectedForBatch.includes(module.id)) {
                      selectedForBatch = selectedForBatch.filter(id => id !== module.id);
                    } else {
                      selectedForBatch = [...selectedForBatch, module.id];
                    }
                  }}
                  class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span class="text-sm text-gray-700 dark:text-gray-300 truncate">{module.id}</span>
              </label>
            {/each}
          </div>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {selectedForBatch.length} / {modules.length} {t('translation.modulesSelected')}
          </p>
        {/if}
      </div>

      <!-- Options -->
      <div class="flex items-center gap-6 mb-4">
        <label class="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" bind:checked={batchForce} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
          <span class="text-sm text-gray-700 dark:text-gray-300">{t('translation.forceReTranslate')}</span>
        </label>
      </div>

      <!-- Progress -->
      {#if Object.keys(batchProgress).length > 0}
        <div class="mb-4 space-y-2">
          <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300">{t('translation.progress')}</h4>
          {#each modules as module (module.id)}
            {@const prog = batchProgress[module.id]}
            {#if prog}
              <div class="flex items-center gap-3">
                <span class="text-xs text-gray-600 dark:text-gray-400 w-32 truncate">{module.id}</span>
                <div class="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-3">
                  <div
                    class="h-3 rounded-full transition-all duration-300
                      {prog.status === 'completed' ? 'bg-green-500' : prog.status === 'failed' ? 'bg-red-500' : 'bg-blue-500'}"
                    style="width: {prog.status === 'completed' || prog.status === 'failed' ? '100%' : '30%'}"
                  ></div>
                </div>
                <span class="text-xs text-gray-500 dark:text-gray-400 w-20 text-right">
                  {#if prog.status === 'completed'}
                    ✅ ({prog.files_translated || 0}/{((prog.files_translated || 0) + (prog.files_skipped || 0) + (prog.files_errored || 0)) || '?'})
                  {:else if prog.status === 'failed'}
                    ❌
                  {:else}
                    ⏳ {t('common.loading')}...
                  {/if}
                </span>
              </div>
            {/if}
          {/each}
        </div>
      {/if}

      <!-- Start Batch -->
      <button
        class="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 font-medium"
        onclick={handleBatchTranslate}
        disabled={translatingModules || selectedForBatch.length === 0}
      >
        {translatingModules ? '⏳ ' + t('translation.translating') : '🚀 ' + t('translation.startBatch')}
        {#if selectedForBatch.length > 0}({selectedForBatch.length}){/if}
      </button>
    </div>
  {/if}

<!-- Single Module Translate Dialog -->
{#if singleTranslateOpen}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onclick={() => { singleTranslateOpen = false; }}
      role="dialog"
      aria-modal="true"
      tabindex="-1">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6"
           role="presentation"
           onclick={(e) => e.stopPropagation()}>
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          {t('translation.translateModule')}
        </h3>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none"
            onclick={() => { singleTranslateOpen = false; }}>✕</button>
      </div>
      <div class="space-y-4">
        <div>
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">{t('translation.moduleLabel')}: <strong>{singleModuleId}</strong></p>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('translation.targetLanguage')}
          </label>
          <select
            bind:value={singleTargetLang}
             class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600
               rounded-lg bg-white dark:bg-gray-700 text-gray-900
               dark:text-white focus:ring-2 focus:ring-blue-500">
          >
            {#each languages as lang}
              <option value={lang}>{lang.toUpperCase()}</option>
            {/each}
          </select>
        </div>
        <label class="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" bind:checked={singleForce} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
          <span class="text-sm text-gray-700 dark:text-gray-300">{t('translation.forceReTranslate')}</span>
        </label>
        <label class="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" bind:checked={singleSkipBackTranslation} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
          <span class="text-sm text-gray-700 dark:text-gray-300">{t('translation.skipBackTranslation')}</span>
        </label>
      </div>
      <div class="flex items-center justify-end gap-3 mt-6">
        <button class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100
             dark:bg-gray-700 rounded-lg hover:bg-gray-200
             dark:hover:bg-gray-600 transition-colors"
            onclick={() => { singleTranslateOpen = false; }}>
          {t('common.cancel')}
        </button>
        <button
          class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          onclick={handleTranslateModule}
          disabled={singleInProgress}
        >
          {singleInProgress ? t('translation.translating') : t('translation.startTranslate')}
        </button>
      </div>
    </div>
  </div>
{/if}
"""

# Find the insertion point - the nav div ends at line 247
nav_end = content.index("</div>\n\n  <!-- Module Translation Status Tab -->")
# Actually find the start of the tab section
tab_section_start = content.index("\n  {#if activeTab")

# The part before the tab section
prefix = content[:tab_section_start]

# The part after the entire broken tab section (from single module dialog onward, but we included it in new_tabs)
# Find where the old broken single dialog section ends
# After the single dialog, there's no more content in the original file
suffix_start = content.index("<!-- Single Module Translate Dialog -->")
suffix = content[suffix_start:]

# But wait - our new_tabs already includes the single dialog section
# So we need to find where the original single dialog section ends
# Find the closing </div> and {/if} of the single dialog
original_single_end = suffix.index("</div>\n{/if}\n") + len("</div>\n{/if}\n")
suffix = suffix[original_single_end:]

result = prefix + new_tabs + suffix

with open("frontend/src/views/TranslationDashboard.svelte", "w") as f:
    f.write(result)

print("Fixed!")

# Verify
with open("frontend/src/views/TranslationDashboard.svelte") as f:
    lines = f.readlines()
opens = 0
closes_if = 0
for line in lines:
    s = line.strip()
    if s.startswith("{#if ") or s.startswith("{:else"):
        opens += 1
    if s == "{/if}":
        closes_if += 1
print(f"If opens: {opens}, If closes: {closes_if}")
