<script>
  /**
   * Dynamic JSON Schema → Svelte form renderer.
   * Handles primitives, enums, booleans, $ref resolution, and simple objects/dicts.
   *
   * @type {{ schema: object, value: object, onchange: (v: object) => void }}
   */
  let { schema = {}, value = $bindable({}), onchange } = $props();

  const properties = $derived(schema.properties || {});
  const defs = $derived(schema['$defs'] || {});
  const required = $derived(new Set(schema.required || []));

  /**
   * Resolve a JSON Schema property, following $ref pointers
   * to inline $defs definitions.
   */
  function resolveProp(prop) {
    if (!prop || !prop['$ref']) return prop;
    const ref = prop['$ref']; // e.g. "#/$defs/PrintFormat"
    const match = ref.match(/^#\/\$defs\/(.+)$/);
    if (match && defs[match[1]]) {
      // Merge the resolved definition with the original prop
      // (original may have "default", "title", "description")
      return { ...defs[match[1]], ...prop };
    }
    return prop;
  }

  function updateField(key, newVal) {
    value = { ...value, [key]: newVal };
    if (onchange) onchange(value);
  }

  function getVal(key, defaultVal) {
    return value[key] !== undefined ? value[key] : defaultVal;
  }
</script>

<div class="config-form space-y-4">
  {#each Object.entries(properties).filter(([k, rp]) => !rp.hidden) as [key, rawProp]}
    {@const prop = resolveProp(rawProp)}
    <div class="form-field">
      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" for="cfg-{key}">
        {prop.title || key}
        {#if required.has(key)}<span class="text-red-500">*</span>{/if}
      </label>

      {#if prop.enum}
        <!-- Enum → select -->
        <select
          id="cfg-{key}"
          class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-200 px-3 py-2 text-sm"
          value={getVal(key, prop.default || '')}
          onchange={(e) => updateField(key, e.target.value)}
        >
          {#each prop.enum as opt}
            <option value={opt}>{opt}</option>
          {/each}
        </select>
      {:else if prop.type === 'boolean'}
        <!-- Boolean → checkbox -->
        <label class="inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={getVal(key, prop.default || false)}
            onchange={(e) => updateField(key, e.target.checked)}
            class="rounded border-gray-300"
          />
          <span class="text-sm text-gray-600 dark:text-gray-400">
            {prop.description || ''}
          </span>
        </label>
      {:else if prop.type === 'integer' || prop.type === 'number'}
        <!-- Number → input number -->
        <input
          id="cfg-{key}"
          type="number"
          value={getVal(key, prop.default || 0)}
          min={prop.minimum}
          max={prop.maximum}
          onchange={(e) => updateField(key, Number(e.target.value))}
          class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-200 px-3 py-2 text-sm"
        />
      {:else if prop.type === 'object' && prop.additionalProperties}
        <!-- Dict → key-value table -->
        <div class="border rounded p-2 bg-gray-50 dark:bg-gray-900">
          {#each Object.entries(getVal(key, {})) as [k, v]}
            <div class="flex gap-2 mb-1">
              <input
                type="text"
                value={k}
                readonly
                class="flex-1 rounded border border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-200 px-2 py-1 text-sm"
              />
              <input
                type="text"
                value={v}
                onchange={(e) => {
                  const obj = { ...getVal(key, {}), [k]: e.target.value };
                  updateField(key, obj);
                }}
                class="flex-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-200 px-2 py-1 text-sm"
              />
            </div>
          {/each}
          {#if Object.keys(getVal(key, {})).length === 0}
            <p class="text-xs text-gray-500 italic">No entries</p>
          {/if}
        </div>
      {:else}
        <!-- String → input text -->
        <input
          id="cfg-{key}"
          type="text"
          value={getVal(key, prop.default || '')}
          placeholder={prop.description || ''}
          onchange={(e) => updateField(key, e.target.value)}
          class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-200 px-3 py-2 text-sm"
        />
      {/if}

      {#if prop.description && prop.type !== 'boolean'}
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{prop.description}</p>
      {/if}
    </div>
  {/each}
</div>
