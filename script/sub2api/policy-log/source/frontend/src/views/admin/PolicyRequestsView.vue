<template>
  <AppLayout>
    <TablePageLayout>
      <template #filters>
        <div class="card space-y-4 p-4 sm:p-5">
          <div class="flex flex-wrap items-center justify-between gap-3 text-sm">
            <div class="flex flex-wrap items-center gap-3">
              <span v-if="result" :class="result.status.enabled ? 'badge badge-success' : 'badge badge-gray'">{{ t(p + (result.status.enabled ? 'enabled' : 'disabled')) }}</span>
              <span v-if="result?.status.enabled" class="text-gray-500 dark:text-gray-400">{{ t(p + 'retention', { days: result.status.retention_days, mb: result.status.max_disk_mb }) }}</span>
            </div>
            <button class="btn btn-secondary btn-sm" :disabled="loading" @click="load">{{ t(p + 'refresh') }}</button>
          </div>
          <p class="text-sm text-gray-500 dark:text-gray-400">{{ t(p + 'policy') }}</p>
          <div v-if="result" class="flex flex-wrap gap-x-6 gap-y-2 text-xs text-gray-500 dark:text-gray-400">
            <span>{{ t(p + 'disk') }}: {{ (result.records.disk_bytes / 1048576).toFixed(2) }} MiB</span>
            <span>{{ t(p + 'written') }}: {{ result.status.runtime.written }}</span>
            <span :class="result.status.runtime.dropped ? 'text-amber-600' : ''">{{ t(p + 'dropped') }}: {{ result.status.runtime.dropped }}</span>
            <span :class="result.status.runtime.write_errors ? 'text-red-600' : ''">{{ t(p + 'writeErrors') }}: {{ result.status.runtime.write_errors }}</span>
          </div>
          <form class="grid grid-cols-1 items-end gap-3 sm:grid-cols-2 xl:grid-cols-4" @submit.prevent="search">
            <label class="block"><span class="input-label">{{ t(p + 'key') }}</span><input v-model.trim="filters.key" class="input" maxlength="200" /></label>
            <label class="block"><span class="input-label">{{ t(p + 'model') }}</span><input v-model.trim="filters.model" class="input" maxlength="200" /></label>
            <div class="block">
              <label for="policy-signal" class="input-label">{{ t(p + 'signal') }}</label>
              <Select id="policy-signal" v-model="filters.error_code" :options="signalOptions" :aria-label="t(p + 'signal')" :searchable="false" />
            </div>
            <div class="hidden xl:block" />
            <label class="block"><span class="input-label">{{ t(p + 'start') }}</span><input v-model="filters.start" type="datetime-local" class="input" /></label>
            <label class="block"><span class="input-label">{{ t(p + 'end') }}</span><input v-model="filters.end" type="datetime-local" class="input" /></label>
            <div class="flex gap-3"><button type="submit" class="btn btn-primary" :disabled="loading">{{ t(p + 'search') }}</button><button type="button" class="btn btn-secondary" :disabled="loading" @click="reset">{{ t(p + 'reset') }}</button></div>
          </form>
          <p class="text-xs text-gray-400">{{ t(p + 'timezone', { zone }) }}</p>
        </div>
        <p v-if="error" role="alert" class="mt-3 text-sm text-red-600">{{ error }}</p>
        <p v-if="result?.records.index_pending" role="status" class="mt-3 text-sm text-amber-600">{{ t(p + 'partial') }}</p>
        <p v-if="result?.records.index_limited" role="alert" class="mt-3 text-sm text-amber-600">{{ t(p + 'limited') }}</p>
        <p v-if="result?.records.unreadable_files" role="alert" class="mt-3 text-sm text-amber-600">{{ t(p + 'unreadable', { n: result.records.unreadable_files }) }}</p>
      </template>
      <template #table>
        <DataTable :columns="columns" :data="result?.records.items || []" :loading="loading" row-key="id">
          <template #cell-recorded_at="{ value }"><span class="whitespace-nowrap">{{ formatTime(value) }}</span></template>
          <template #cell-owner="{ row }"><div class="max-w-[220px] truncate font-medium" :title="row.api_key_name">{{ row.api_key_name || '—' }}</div><div class="mt-1 text-xs text-gray-400">Key #{{ row.api_key_id }} · {{ t(p + 'user') }} #{{ row.user_id }}</div><div class="mt-1 text-xs text-gray-400">{{ row.group_name || '—' }}</div></template>
          <template #cell-error_code="{ value }"><span class="rounded bg-amber-50 px-2 py-1 font-mono text-xs text-amber-800 dark:bg-amber-900/20 dark:text-amber-300">{{ value }}</span></template>
          <template #cell-actions="{ row }"><button class="font-medium text-primary-600 dark:text-primary-400" @click="openDetail(row.id)">{{ t(p + 'detail') }}</button></template>
          <template #empty><div class="px-5 py-12 text-center"><Icon name="shield" size="xl" class="mx-auto mb-3 text-gray-300" /><p class="text-sm font-medium text-gray-600 dark:text-gray-300">{{ t(p + 'empty') }}</p><p class="mx-auto mt-2 max-w-xl text-xs leading-6 text-gray-400">{{ t(p + 'emptyHint') }}</p></div></template>
        </DataTable>
      </template>
      <template #pagination>
        <p class="mb-2 text-xs text-gray-400">{{ t(p + 'keyHint') }}</p>
        <Pagination v-if="result && result.records.total > 0" :total="result.records.total" :page="page" :page-size="20" :show-page-size-selector="false" @update:page="changePage" />
      </template>
    </TablePageLayout>
    <BaseDialog :show="!!selected" :title="t(p + 'detail')" width="extra-wide" @close="closeDetail">
      <p v-if="detailLoading" role="status">{{ t(p + 'loading') }}</p>
      <p v-if="detailError" role="alert" class="text-red-600">{{ detailError }}</p>
      <template v-if="detail">
        <details class="mb-5 rounded-lg border border-gray-200 p-3 dark:border-dark-600"><summary class="cursor-pointer text-sm font-medium">{{ t(p + 'metadata') }}</summary><pre class="mt-3 max-h-60 overflow-auto whitespace-pre-wrap break-all text-xs">{{ metadata }}</pre></details>
        <h4 class="mb-3 font-medium">{{ t(p + 'body') }}</h4>
        <p v-if="detail.preview_truncated" class="mb-3 text-sm text-amber-600">{{ t(p + 'preview') }}</p>
        <p v-if="detail.record.body_encoding === 'base64'" class="mb-3 text-sm text-gray-500">{{ t(p + 'raw') }}</p>
        <pre data-testid="policy-body" class="max-h-[50vh] overflow-auto whitespace-pre-wrap break-all rounded-lg bg-gray-50 p-4 font-mono text-xs leading-6 dark:bg-dark-900">{{ bodyText }}</pre>
      </template>
      <template #footer><button v-if="detail" class="btn btn-primary" :disabled="downloading" @click="download">{{ t(p + 'download') }}</button></template>
    </BaseDialog>
  </AppLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { policyRequestsAPI, type PolicyDetail, type PolicyList, type PolicyQuery } from '@/api/admin/policyRequests'
import AppLayout from '@/components/layout/AppLayout.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import DataTable from '@/components/common/DataTable.vue'
import Pagination from '@/components/common/Pagination.vue'
import BaseDialog from '@/components/common/BaseDialog.vue'
import Select from '@/components/common/Select.vue'
import Icon from '@/components/icons/Icon.vue'

const { t } = useI18n()
const p = 'admin.policyRequests.'
const zone = Intl.DateTimeFormat().resolvedOptions().timeZone
const signals = ['cyber_policy', 'content_policy', 'content_policy_violation', 'invalid_prompt', 'content_filter', 'structured_refusal']
const signalOptions = computed(() => [{ value: '', label: t(p + 'all') }, ...signals.map(code => ({ value: code, label: code }))])
const filters = reactive({ key: '', model: '', error_code: '', start: '', end: '' })
const page = ref(1)
const result = ref<PolicyList | null>(null)
const loading = ref(false)
const error = ref('')
const selected = ref('')
const detail = ref<PolicyDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref('')
const downloading = ref(false)
let applied: Omit<PolicyQuery, 'page'> = { page_size: 20 }
let listController: AbortController | undefined
let detailController: AbortController | undefined
const columns = computed(() => [
  { key: 'recorded_at', label: t(p + 'time') }, { key: 'owner', label: t(p + 'owner') },
  { key: 'model', label: t(p + 'model') }, { key: 'error_code', label: t(p + 'signal') },
  { key: 'account_id', label: t(p + 'account') }, { key: 'protocol', label: t(p + 'protocol') },
  { key: 'actions', label: '' }
])
const formatTime = (value: string) => new Date(value).toLocaleString(undefined, { hour12: false })
const metadata = computed(() => { const data = { ...detail.value?.record }; delete data.body; return JSON.stringify(data, null, 2) })
const bodyText = computed(() => {
  const text = detail.value?.body_preview || ''
  if (!detail.value?.preview_truncated && detail.value?.record.body_encoding !== 'base64') {
    try { return JSON.stringify(JSON.parse(text), null, 2) } catch { /* Raw body remains visible. */ }
  }
  return text
})
async function load() {
  listController?.abort()
  const controller = new AbortController(); listController = controller
  loading.value = true; error.value = ''
  try { const data = await policyRequestsAPI.list({ ...applied, page: page.value }, controller.signal); if (!controller.signal.aborted) result.value = data }
  catch { if (!controller.signal.aborted) { result.value = null; error.value = t(p + 'error') } }
  finally { if (!controller.signal.aborted) loading.value = false }
}
function search() {
  if (filters.start && filters.end && new Date(filters.start) >= new Date(filters.end)) { error.value = t(p + 'invalidTime'); return }
  applied = { page_size: 20, key: filters.key, model: filters.model, error_code: filters.error_code,
    start_time: filters.start ? new Date(filters.start).toISOString() : undefined,
    end_time: filters.end ? new Date(filters.end).toISOString() : undefined }
  page.value = 1; void load()
}
function reset() { Object.assign(filters, { key: '', model: '', error_code: '', start: '', end: '' }); search() }
function changePage(value: number) { page.value = value; void load() }
async function openDetail(id: string) {
  detailController?.abort()
  const controller = new AbortController(); detailController = controller
  selected.value = id; detail.value = null; detailError.value = ''; detailLoading.value = true
  try { const data = await policyRequestsAPI.get(id, controller.signal); if (!controller.signal.aborted) detail.value = data }
  catch { if (!controller.signal.aborted) detailError.value = t(p + 'error') }
  finally { if (!controller.signal.aborted) detailLoading.value = false }
}
function closeDetail() { detailController?.abort(); selected.value = ''; detail.value = null; detailError.value = '' }
async function download() {
  const id = selected.value; downloading.value = true
  try {
    const blob = await policyRequestsAPI.download(id)
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `policy-request-${id.slice(0, 12)}.txt`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch { if (selected.value === id) detailError.value = t(p + 'downloadError') }
  finally { downloading.value = false }
}
onMounted(load)
onUnmounted(() => { listController?.abort(); detailController?.abort() })
</script>
