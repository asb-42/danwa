<script>
  /**
   * DebateReportPanel — Report generation UI for completed debates.
   *
   * Shown at the bottom of the final consensus section.
   */
  import { tStore } from '../../lib/i18n/index.js';
  import { generateReport, getReportStatus, downloadReport } from '../../lib/api.js';

  let { debateId = null } = $props();

  let t = $derived($tStore);

  let reportFormat = $state('docx');
  let reportGenerating = $state(false);
  let reportJobId = $state(null);
  let reportError = $state(null);
  let reportPollTimer = $state(null);

  import { onDestroy } from 'svelte';
  onDestroy(() => {
    if (reportPollTimer) clearInterval(reportPollTimer);
  });

  async function handleGenerateReport() {
    if (!debateId) return;
    reportGenerating = true;
    reportError = null;
    reportJobId = null;
    try {
      const result = await generateReport(debateId, reportFormat);
      reportJobId = result.job_id;
      reportPollTimer = setInterval(async () => {
        try {
          const status = await getReportStatus(reportJobId);
          if (status.status === 'completed') {
            clearInterval(reportPollTimer);
            reportPollTimer = null;
            reportGenerating = false;
            try {
              const blob = await downloadReport(reportJobId);
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `report-${debateId.substring(0, 8)}.${reportFormat}`;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              URL.revokeObjectURL(url);
            } catch (dlErr) {
              reportError = dlErr.message || t('report.status.failed');
            }
          } else if (status.status === 'failed') {
            clearInterval(reportPollTimer);
            reportPollTimer = null;
            reportGenerating = false;
            reportError = status.error || t('report.status.failed');
          }
        } catch (pollErr) {
          if (import.meta.env.DEV) console.warn('[Report] Poll error:', pollErr);
        }
      }, 2000);
    } catch (err) {
      reportError = err.message;
      reportGenerating = false;
    }
  }
</script>

<div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
  <div class="flex items-center gap-3 flex-wrap">
    <label for="report-format" class="text-sm font-medium text-gray-700 dark:text-gray-300">
      📄 {t('report.generate')}:
    </label>
    <select
      id="report-format"
      bind:value={reportFormat}
      class="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg
             bg-white dark:bg-gray-700 text-gray-900 dark:text-white
             focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
    >
      <option value="docx">DOCX</option>
      <option value="pdf">PDF</option>
      <option value="odf">ODF</option>
    </select>
    <button
      class="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:hover:bg-blue-600
             transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
      onclick={handleGenerateReport}
      disabled={reportGenerating}
    >
      {#if reportGenerating}
        <span class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
        {t('report.status.pending')}
      {:else}
        ⬇ {t('report.download')}
      {/if}
    </button>
  </div>
  {#if reportError}
    <p class="mt-2 text-sm text-red-600 dark:text-red-400">{reportError}</p>
  {/if}
</div>
