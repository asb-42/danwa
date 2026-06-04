<script>
	import { onMount } from 'svelte';
	import { getLLMProfiles, getDebate, forkDebate } from '../../lib/api.js';
	import { tStore } from '../../lib/i18n/index.js';

	let { debateId, navigate = () => {} } = $props();

	let t = $derived($tStore);

	let isLoading = $state(false);
	let isSaving = $state(false);
	let statusMessage = $state('');
	let error = $state(null);

	let forkReasonOptions = [
		{ value: 'consensus_breakdown', label: t('fork.reason.consensus_breakdown') },
		{ value: 'new_perspective', label: t('fork.reason.new_perspective') },
		{ value: 'branching', label: t('fork.reason.branching') },
	];

	let debate = $state(null);
	let form = $state({
		newTitle: '',
		forkFromRound: null,
		forkReason: '',
		modifiedPersonas: {},
		modifiedPromptVariant: '',
	});

	let llmProfiles = $state([]);
	let agentPersonas = $state([]);
	let personaOptions = $state([]); // For dropdowns

	const loadDebate = async () => {
		isLoading = true;
		error = null;
		try {
			const [debateData, profiles] = await Promise.all([
				getDebate(debateId),
				getLLMProfiles(),
			]);
			debate = debateData;
			llmProfiles = profiles;
		} catch (err) {
			error = err.message;
		} finally {
			isLoading = false;
		}
	};

	const handleSave = async () => {
		isSaving = true;
		error = null;
		statusMessage = '';
		try {
			await forkDebate(debateId, {
				newTitle: form.newTitle.trim() || undefined,
				forkFromRound: form.forkFromRound,
				forkReason: form.forkReason,
				modifiedPersonas: Object.keys(form.modifiedPersonas).length > 0
					? form.modifiedPersonas
					: undefined,
				modifiedPromptVariant:
					form.modifiedPromptVariant.trim() || undefined,
			});
			statusMessage = `✓ ${t('projects.projectUpdated')}`;
			// Navigate to the new debate after a short delay
			setTimeout(() => {
				navigate('debate');
			}, 1500);
		} catch (err) {
			error = err.message;
		} finally {
			isSaving = false;
		}
	};

	const handleCancel = () => {
		navigate('debate');
	};

	onMount(async () => {
		await loadDebate();
	});
</script>

{#if error}
	<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
		{error}
	</div>
{/if}

{#if statusMessage}
	<div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-700 dark:text-green-300" role="status">
		{statusMessage}
	</div>
{/if}

{#if isLoading}
	<div class="flex items-center justify-center h-32">
		<p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
	</div>
{:else}
	<div class="space-y-6">
		<!-- Header -->
		<div class="flex items-center gap-3">
			<button
				class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
				onclick={() => navigate('debate')}
				title={t('common.back')}
			>
				←
			</button>
			<div class="flex-1 min-w-0">
				<h2 class="text-2xl font-bold text-gray-800 dark:text-white truncate">
					{t('debate.title')} #{debate?.id ?? '...'}
				</h2>
				<p class="text-sm text-gray-500 dark:text-gray-400">
					{t('debate.forkTitle')}
				</p>
			</div>
		</div>

		<!-- Form -->
		<div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
			<div class="p-6 space-y-6">

				<!-- New Title -->
				<div>
					<label for="new-title" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						{t('fork.newTitle')}
					</label>
					<input
						id="new-title"
						type="text"
						bind:value={form.newTitle}
						placeholder={t('fork.newTitlePlaceholder')}
						class="flex-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
								bg-white dark:bg-gray-700 text-gray-900 dark:text-white
								focus:ring-2 focus:ring-blue-500 focus:border-blue-500
								placeholder:text-gray-400 dark:placeholder:text-gray-500"
					/>
				</div>

				<!-- Fork From Round -->
				<div>
					<label for="fork-from-round" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						{t('fork.forkFromRound')}
					</label>
					<div class="flex items-center gap-2">
						<input
							id="fork-from-round"
							type="number"
							min="1"
							max={debate?.max_rounds ?? 20}
							bind:value={form.forkFromRound}
							placeholder={t('projects.globalDefault')}
							class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
									bg-white dark:bg-gray-700 text-gray-900 dark:text-white
									focus:ring-2 focus:ring-blue-500 focus:border-blue-500
									placeholder:text-gray-400 dark:placeholder:text-gray-500"
						/>
						{#if form.forkFromRound !== null && form.forkFromRound !== ''}
							<button
								class="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
								onclick={() => (form.forkFromRound = null)}
								title={t('projects.globalDefault')}
							>
								✕
							</button>
						{/if}
					</div>
				</div>

				<!-- Fork Reason -->
				<div>
					<label for="fork-reason" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						{t('fork.forkReason')}
					</label>
					<select
						id="fork-reason"
						bind:value={form.forkReason}
						class="flex-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
								bg-white dark:bg-gray-700 text-gray-900 dark:text-white
								focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
					>
						<option value="">{t('projects.globalDefault')}</option>
						{#each forkReasonOptions as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</div>

				<!-- Modified Personas -->
				<div>
					<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						{t('fork.modifiedPersonas')}
					</label>
					<p class="text-xs text-gray-500 dark:text-gray-400 mb-2">
						{t('fork.modifiedPersonasHint')}
					</p>
					<div class="space-y-3">
						{#each ['strategist', 'critic', 'optimizer', 'moderator'] as role}
							<div class="flex items-center gap-4">
								<label class="w-20 text-sm font-medium text-gray-700 dark:text-gray-300">
									{t(`agent.${role}`)}
								</label>
								<select
									class="flex-1 min-w-0 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
											bg-white dark:bg-gray-700 text-gray-900 dark:text-white
											focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
									onchange={(e) => {
										const value = e.target.value;
										if (value) {
											form.modifiedPersonas = {
												...form.modifiedPersonas,
												[role]: value,
											};
										} else {
											const { [role]: _, ...rest } = form.modifiedPersonas;
											form.modifiedPersonas = rest;
										}
									}}
								>
									<option value="">— {t('projects.globalDefault')} —</option>
									{#each personaOptions as persona}
										{#if persona.role === role}
											<option value={persona.id}>{persona.name}</option>
										{/if}
									{/each}
								</select>
							</div>
						{/each}
					</div>
				</div>

				<!-- Modified Prompt Variant -->
				<div>
					<label for="modified-prompt-variant" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						{t('fork.modifiedPromptVariant')}
					</label>
					<p class="text-xs text-gray-500 dark:text-gray-400 mb-2">
						{t('fork.modifiedPromptVariantHint')}
					</p>
					<input
						id="modified-prompt-variant"
						type="text"
						bind:value={form.modifiedPromptVariant}
						placeholder={t('projects.globalDefault')}
						class="flex-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
								bg-white dark:bg-gray-700 text-gray-900 dark:text-white
								focus:ring-2 focus:ring-blue-500 focus:border-blue-500
								placeholder:text-gray-400 dark:placeholder:text-gray-500"
					/>
					{#if form.modifiedPromptVariant !== null && form.modifiedPromptVariant !== ''}
						<button
							class="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
							onclick={() => (form.modifiedPromptVariant = '')}
							title={t('projects.globalDefault')}
						>
							✕
						</button>
					{/if}
				</div>

			</div>

			<!-- Footer -->
			<div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
				<button
					class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
					onclick={handleCancel}
				>
					{t('common.cancel')}
				</button>
				<button
					class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:hover:bg-blue-600 transition-colors
							disabled:opacity-50 disabled:cursor-not-allowed"
					onclick={handleSave}
					disabled={isSaving}
				>
					{isSaving ? '...' : t('fork.submit')}
				</button>
			</div>
		</div>
	</div>
{/if}
