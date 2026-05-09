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
</script>

{#if hasCapabilities}
  <div class="a2a-capabilities">
    <h4>{t('a2a.capabilities.title')}</h4>

    {#if capabilities.name}
      <div class="field">
        <span class="label">Name:</span>
        <span class="value">{capabilities.name}</span>
      </div>
    {/if}

    {#if capabilities.description}
      <div class="field">
        <span class="label">Description:</span>
        <span class="value">{capabilities.description}</span>
      </div>
    {/if}

    {#if capabilities.version}
      <div class="field">
        <span class="label">{t('a2a.capabilities.version')}:</span>
        <span class="value">{capabilities.version}</span>
      </div>
    {/if}

    {#if skills.length > 0}
      <div class="field">
        <span class="label">{t('a2a.capabilities.skills')}:</span>
        <ul class="skill-list">
          {#each skills as skill}
            <li>
              <strong>{skill.name || skill.id || '—'}</strong>
              {#if skill.description}
                <span class="skill-desc">{skill.description}</span>
              {/if}
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if inputModes.length > 0}
      <div class="field">
        <span class="label">{t('a2a.capabilities.inputModes')}:</span>
        <span class="value">{inputModes.join(', ')}</span>
      </div>
    {/if}

    {#if outputModes.length > 0}
      <div class="field">
        <span class="label">{t('a2a.capabilities.outputModes')}:</span>
        <span class="value">{outputModes.join(', ')}</span>
      </div>
    {/if}
  </div>
{/if}

<style>
  .a2a-capabilities {
    padding: 0.75rem;
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 6px;
    margin-top: 0.5rem;
  }
  h4 {
    margin: 0 0 0.5rem 0;
    font-size: 0.85rem;
    color: #0369a1;
  }
  .field {
    margin-bottom: 0.4rem;
    font-size: 0.8rem;
  }
  .label {
    color: #666;
    margin-right: 0.25rem;
  }
  .value {
    color: #333;
  }
  .skill-list {
    list-style: none;
    padding: 0;
    margin: 0.25rem 0 0 0;
  }
  .skill-list li {
    padding: 0.2rem 0;
  }
  .skill-desc {
    display: block;
    color: #666;
    font-size: 0.75rem;
  }
</style>
