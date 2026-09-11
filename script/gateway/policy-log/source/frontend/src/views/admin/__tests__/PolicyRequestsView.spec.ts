import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import View from '../PolicyRequestsView.vue'
import Select from '@/components/common/Select.vue'
const api = vi.hoisted(() => ({ list: vi.fn(), get: vi.fn(), download: vi.fn() }))
vi.mock('@/api/admin/policyRequests', () => ({ policyRequestsAPI: api }))
vi.mock('vue-i18n', async () => ({ ...await vi.importActual<typeof import('vue-i18n')>('vue-i18n'), useI18n: () => ({ t: (key: string) => key }) }))
const row = { id: 'a'.repeat(64), api_key_id: 65, api_key_name: 'Test owner', user_id: 9, recorded_at: '2026-09-03T03:00:00Z', error_code: 'cyber_policy', model: 'test-model', protocol: 'http', account_id: 51 }
const listing = { records: { items: [row], total: 1, index_pending: false, disk_bytes: 1024 }, status: { enabled: true, retention_days: 30, max_disk_mb: 1024, runtime: { written: 1, dropped: 0, write_errors: 0 } } }
function view() { return mount(View, { global: { stubs: { AppLayout: { template: '<div><slot /></div>' }, BaseDialog: { props: ['show'], template: '<div v-if="show"><slot /><slot name="footer" /></div>' }, Icon: true, Pagination: true } } }) }
describe('Policy requests admin view', () => {
 beforeEach(() => { vi.clearAllMocks(); api.list.mockResolvedValue(listing); api.get.mockResolvedValue({ record: row, body_preview: '{"input":"<img src=x onerror=alert(1)>"}', preview_truncated: false }) })
 it('loads metadata only and fetches escaped body on explicit detail', async () => {
  const w=view(); await flushPromises(); expect(api.get).not.toHaveBeenCalled()
  const button=w.findAll('button').find(x=>x.text()==='admin.policyRequests.detail')!; await button.trigger('click');await flushPromises()
  expect(api.get).toHaveBeenCalledWith(row.id,expect.any(AbortSignal));expect(w.get('[data-testid="policy-body"]').text()).toContain('<img src=x onerror=alert(1)>');expect(w.find('[data-testid="policy-body"] img').exists()).toBe(false);w.unmount()
 })
 it('submits combined filters and resets the page',async()=>{const w=view();await flushPromises();await w.findAll('input')[0].setValue('65');await w.findAll('input')[1].setValue('test');w.getComponent(Select).vm.$emit('update:modelValue','cyber_policy');await w.get('form').trigger('submit');await flushPromises();expect(api.list).toHaveBeenLastCalledWith(expect.objectContaining({page:1,key:'65',model:'test',error_code:'cyber_policy'}),expect.any(AbortSignal));w.unmount()})
 it('clears old rows on failed refresh',async()=>{const w=view();await flushPromises();api.list.mockRejectedValueOnce(new Error('offline'));await w.findAll('button')[0].trigger('click');await flushPromises();expect(w.find('[role="alert"]').text()).toContain('error');expect(w.text()).not.toContain('Test owner');w.unmount()})
 it('discards an outstanding body when unmounted',async()=>{let resolve!: (x:unknown)=>void;api.get.mockReturnValue(new Promise(r=>{resolve=r}));const w=view();await flushPromises();await w.findAll('button').find(x=>x.text()==='admin.policyRequests.detail')!.trigger('click');const signal=api.get.mock.calls[0][1];w.unmount();expect(signal.aborted).toBe(true);resolve({record:row,body_preview:'late',preview_truncated:false});await flushPromises()})
})
