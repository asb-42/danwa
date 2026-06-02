<script>
  import { tStore } from '../../lib/i18n/index.js';

  let {
    personas = [],
    selectedPersonas = {},
    blueprintRoleDefIds = new Set(),
    onCreate = () => {},
    onEdit = () => {},
    onDelete = () => {},
    onSelectPersona = () => {},
  } = $props();

  let t = $derived($tStore);

  function getPersonasByRole(role) {
    return personas.filter(p => p.role === role);
  }

  function isBlueprintManaged(personaId) {
    return blueprintRoleDefIds.has(personaId);
  }
</script>

<div class="space-y-4">
  {#each ['strategist', 'critic', 'optimizer', 'moderator'] as role}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
      <div class="flex items-center justify-between mb-3">
        <h4 class="text-md font-semibold text-gray-800 dark:text-white capitalize">{t(`agent.${role}`)}</h4>
        <button class="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors" onclick={() => onCreate(role)}>
          + {t('config.createPersona')}
        </button>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {#each getPersonasByRole(role) as persona}
          <div class="p-3 rounded-lg border transition-colors relative
            {selectedPersonas[role] === persona.id
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
              : 'border-gray-200 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'}">
            <div class="cursor-pointer" onclick={() => { onSelectPersona(role, persona.id); }}
              onkeydown={(e) => { if (e.key === 'Enter') onSelectPersona(role, persona.id); }}
              role="button" tabindex="0">
              <div class="flex items-center justify-between mb-1">
                <span class="font-medium text-sm text-gray-800 dark:text-white">{persona.name}</span>
                <span class="flex items-center gap-1">
                  {#if isBlueprintManaged(persona.id)}
                    <span class="text-xs px-1.5 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded" title="{t('config.managedByBlueprint') || 'Managed by Blueprint Canvas'}">🧩</span>
                  {/if}
                  {#if selectedPersonas[role] === persona.id}
                    <span class="text-xs text-green-600 dark:text-green-400">✓</span>
                  {/if}
                </span>
              </div>
              {#if persona.description}
                <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">{persona.description}</p>
              {/if}
              <div class="flex flex-wrap gap-1">
                {#each persona.tags as tag}
                  <span class="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded">{tag}</span>
                {/each}
              </div>
            </div>
            <div class="flex gap-1 mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
              <button class="text-xs px-2 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors" onclick={() => onEdit(persona)}>
                {t('common.edit')}
              </button>
              <button class="text-xs px-2 py-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors" onclick={() => onDelete(persona.id, persona.name)}>
                {t('common.delete')}
              </button>
            </div>
          </div>
        {:else}
          <p class="text-sm text-gray-500 dark:text-gray-400 col-span-full">{t('config.noProfiles')}</p>
        {/each}
      </div>
    </div>
  {/each}
</div>
