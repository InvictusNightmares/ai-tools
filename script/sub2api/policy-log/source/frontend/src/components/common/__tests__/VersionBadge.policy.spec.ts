import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import VersionBadge from '../VersionBadge.vue'

const store = reactive({
  versionLoading: false,
  currentVersion: '0.2.0+policy-log.6',
  latestVersion: '0.2.0+policy-log.7',
  hasUpdate: false,
  buildType: 'release',
  releaseInfo: null,
  versionWarning: '',
  versionNeedRestart: true,
  fetchVersion: vi.fn(async (): Promise<{need_restart: boolean}> => ({need_restart: store.versionNeedRestart})),
  clearVersionCache: vi.fn()
})
vi.mock('@/stores', () => ({ useAuthStore: () => ({isAdmin: true}), useAppStore: () => store }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({t: (key: string) => key}) }))
vi.mock('@/api/admin/system', () => ({performUpdate: vi.fn(), restartService: vi.fn(), getRollbackVersions: vi.fn(), rollback: vi.fn()}))
vi.mock('@/composables/useClipboard', () => ({useClipboard: () => ({copied: false, copyToClipboard: vi.fn()})}))

describe('Custom update restart recovery', () => {
  beforeEach(() => {store.versionNeedRestart = true; store.versionWarning = ''; vi.clearAllMocks()})

  it('restores the restart action after reopening the page', async () => {
    const wrapper = mount(VersionBadge, {global: {stubs: {Icon: true}}})
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('version.restartRequired')
    expect(wrapper.text()).toContain('version.restartNow')
    expect(wrapper.text()).not.toContain('version.retry')
    wrapper.unmount()
  })

  it('keeps restart available after refreshing an already pending update', async () => {
    const wrapper = mount(VersionBadge, {global: {stubs: {Icon: true}}})
    await wrapper.find('button').trigger('click')
    await wrapper.find('button[title="version.refresh"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('version.restartRequired')
    expect(wrapper.text()).toContain('version.restartNow')
    wrapper.unmount()
  })

  it('shows a failed build warning rather than an up-to-date success', async () => {
    store.versionNeedRestart = false
    store.versionWarning = 'build failed; current service remains available'
    const wrapper = mount(VersionBadge, {global: {stubs: {Icon: true}}})
    await wrapper.find('button').trigger('click')
    expect(wrapper.text()).toContain(store.versionWarning)
    expect(wrapper.text()).not.toContain('version.upToDate')
    wrapper.unmount()
  })
})
