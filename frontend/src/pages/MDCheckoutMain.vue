<template>
  <q-page class="q-pa-md" :class="{ 'bg-grey-1': !$q.dark.isActive }">
    <q-card flat bordered class="rounded-borders">
      <q-card-section :class="$q.dark.isActive ? 'bg-dark text-white' : 'bg-primary text-white'">
        <div class="text-h6">MD Checkout Main Screen</div>
        <div class="text-caption">Select provider and date to load patients</div>
      </q-card-section>

      <q-card-section class="q-pa-md">
        <div class="row q-col-gutter-md">
          <!-- Provider and Date Selection -->
          <div class="col-12 col-md-6">
            <q-select
              dense
              label="Provider"
              v-model="provider"
              :options="filteredProviderOptions"
              option-label="label"
              option-value="value"
              emit-value
              map-options
              outlined
              class="rounded-borders"
              use-input
              input-debounce="300"
              @filter="filterProviders"
              @update:model-value="onProviderChange"
              clearable
              fill-input
              hide-selected
            >
              <template v-slot:no-option>
                <q-item>
                  <q-item-section class="text-grey">No providers found</q-item-section>
                </q-item>
              </template>
              <template v-slot:option="scope">
                <q-item v-bind="scope.itemProps">
                  <q-item-section>
                    <q-item-label>{{ scope.opt.label }}</q-item-label>
                    <q-item-label caption>ID: {{ scope.opt.value }}</q-item-label>
                  </q-item-section>
                </q-item>
              </template>
            </q-select>
          </div>
          <div class="col-12 col-md-6">
            <q-input
              dense
              label="Appointment Date"
              v-model="date"
              type="date"
              outlined
              class="rounded-borders"
              @update:model-value="onDateChange"
            />
          </div>
          <div class="col-12">
            <div class="text-caption q-mt-xs text-grey-7">
              <q-icon name="info" size="xs" /> Showing patients from all locations
            </div>
            <div class="row justify-end q-mt-md">
              <q-btn
                label="Search"
                icon="search"
                color="primary"
                class="q-pl-sm q-pa-sm"
                @click="onSearch"
                :loading="isSearching"
                rounded
                dense
                push
              />
              <q-btn
                label="Reset"
                icon="refresh"
                class="q-ml-sm q-pa-sm"
                color="primary"
                @click="onReset"
                :disable="isSearching"
                rounded
                dense
                push
              />
            </div>
          </div>
        </div>

        <q-separator class="q-my-md" />

        <!-- Results Section -->
        <div class="q-mb-md">
          <q-card flat bordered class="rounded-borders">
            <q-card-section class="q-pa-sm">
              <div class="row items-center q-col-gutter-sm q-mb-sm">
                <div class="col">
                  <div class="text-subtitle2">Patient Results</div>
                  <div class="text-caption text-grey-7">
                    {{ patientResults.length }} matching
                    {{ patientResults.length === 1 ? 'patient' : 'patients' }}
                  </div>
                </div>
                <div class="col-auto">
                  <q-btn
                    dense
                    flat
                    icon="refresh"
                    color="primary"
                    :disable="isSearching"
                    @click="onSearch"
                  >
                    <q-tooltip>Refresh results</q-tooltip>
                  </q-btn>
                </div>
              </div>

              <q-banner v-if="!hasSearched" class="bg-blue-1 q-mb-sm" rounded>
                <template v-slot:avatar>
                  <q-icon name="info" color="primary" />
                </template>
                Patient data will be loaded from the client API. Select a provider and date, then click Search.
                <br />
                <span class="text-caption text-grey-7">Demo mode: showing sample patients.</span>
              </q-banner>

              <q-table
                flat
                bordered
                dense
                :rows="patientResults"
                :columns="patientColumns"
                row-key="rowKey"
                :loading="isSearching"
                :filter="searchText"
                :rows-per-page-options="[0]"
                :pagination="{ rowsPerPage: 0 }"
                no-data-label="No patients found. Select a provider and date, then click Search."
                :wrap-cells="false"
              >
                <template v-slot:body-cell-actions="props">
                  <q-td :props="props">
                    <div class="row no-wrap q-gutter-xs">
                      <q-btn
                        dense
                        outline
                        color="secondary"
                        label="AI Scribe"
                        size="sm"
                        @click.stop="onAIScribe(props.row)"
                      />
                    </div>
                  </q-td>
                </template>
                <template v-slot:top-right>
                  <q-input
                    dense
                    debounce="300"
                    v-model="searchText"
                    placeholder="Search"
                    class="q-mr-md"
                  >
                    <template v-slot:append>
                      <q-icon name="search" />
                    </template>
                  </q-input>
                </template>
              </q-table>
            </q-card-section>
          </q-card>
        </div>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuasar } from 'quasar'

const $q = useQuasar()
const router = useRouter()

// ── Stub providers (will be replaced by client API) ─────────────────────
const STUB_PROVIDERS = [
  { label: 'Caleb Ademiloye, NP', value: 'caleb_ademiloye' },
  { label: 'Jebeh Baimba, NP', value: 'jebeh_baimba' },
  { label: 'Fese Bokosah, NP', value: 'fese_bokosah' },
  { label: 'Irine Breslaw, PA', value: 'irine_breslaw' },
  { label: 'Tiffany Halliburton, NP', value: 'tiffany_halliburton' },
  { label: 'Mariama Koroma, NP', value: 'mariama_koroma' },
  { label: 'Antonina Mudimba, NP', value: 'antonina_mudimba' },
  { label: 'Paul Peace, NP', value: 'paul_peace' },
  { label: 'Lourdes Rivera, NP', value: 'lourdes_rivera' },
  { label: 'Dan Schechter, PA', value: 'dan_schechter' },
  { label: 'Rajul Shah, PA', value: 'rajul_shah' },
]

// ── Stub patients (will be replaced by client API) ───────────────────────
function buildStubPatients(providerValue, dateStr) {
  if (!providerValue || !dateStr) return []
  const providerLabel = STUB_PROVIDERS.find(p => p.value === providerValue)?.label || providerValue
  const time = (h, m) => {
    const suffix = h >= 12 ? 'pm' : 'am'
    const hr = h > 12 ? h - 12 : h
    return `${dateStr} ${hr}:${String(m).padStart(2, '0')}${suffix}`
  }
  return [
    { guarantor_id: 'G100001', appointment_id: 'A100001', account_number: '100001', patient_name: 'Smith, John', appointment_date: time(10, 0), case_name: 'MVA 2025', case_number: 'C100001', location_name: 'COLUMBIA', provider_name: providerLabel, provider_id: providerValue, injury_date: '2025-11-15', d_o_b: '1975-03-20', encounter_id: `ENC-${dateStr}-001` },
    { guarantor_id: 'G100002', appointment_id: 'A100002', account_number: '100002', patient_name: 'Johnson, Mary', appointment_date: time(10, 30), case_name: 'Slip & Fall', case_number: 'C100002', location_name: 'CAMP SPRINGS', provider_name: providerLabel, provider_id: providerValue, injury_date: '2025-12-01', d_o_b: '1960-07-14', encounter_id: `ENC-${dateStr}-002` },
    { guarantor_id: 'G100003', appointment_id: 'A100003', account_number: '100003', patient_name: 'Williams, Robert', appointment_date: time(11, 0), case_name: 'Work Injury', case_number: 'C100003', location_name: 'DUNDALK', provider_name: providerLabel, provider_id: providerValue, injury_date: '2026-01-10', d_o_b: '1985-11-30', encounter_id: `ENC-${dateStr}-003` },
    { guarantor_id: 'G100004', appointment_id: 'A100004', account_number: '100004', patient_name: 'Brown, Patricia', appointment_date: time(11, 30), case_name: 'Pedestrian vs Vehicle', case_number: 'C100004', location_name: 'COLUMBIA', provider_name: providerLabel, provider_id: providerValue, injury_date: '2026-01-23', d_o_b: '1990-05-22', encounter_id: `ENC-${dateStr}-004` },
  ].map((r, i) => ({ ...r, rowKey: `row_${i}` }))
}

const provider = ref(null)
const providerOptions = ref([...STUB_PROVIDERS])
const filteredProviderOptions = ref([...STUB_PROVIDERS])
const date = ref(new Date().toISOString().slice(0, 10))
const isSearching = ref(false)
const patientResults = ref([])
const searchText = ref('')
const hasSearched = ref(false)

const patientColumns = [
  { name: 'patient', label: 'Patient', field: 'patient_name', align: 'left', sortable: true },
  { name: 'appointment', label: 'Appointment', field: 'appointment_date', align: 'left', sortable: true },
  { name: 'account_number', label: 'PM Account', field: 'account_number', align: 'left', sortable: true },
  { name: 'case_name', label: 'Case Name', field: 'case_name', align: 'left', sortable: true },
  { name: 'provider_name', label: 'Provider', field: 'provider_name', align: 'left', sortable: true },
  { name: 'location_name', label: 'Location', field: 'location_name', align: 'left', sortable: true },
  { name: 'actions', label: 'Actions', field: 'actions', align: 'center', sortable: false },
]

function filterProviders(val, update) {
  update(() => {
    if (val === '') {
      filteredProviderOptions.value = providerOptions.value
    } else {
      const needle = val.toLowerCase()
      filteredProviderOptions.value = providerOptions.value.filter(
        p => p.label.toLowerCase().includes(needle) || p.value.toLowerCase().includes(needle),
      )
    }
  })
}

function onProviderChange(value) {
  if (value && date.value) onSearch()
}

function onDateChange(value) {
  if (value && provider.value) onSearch()
}

function onSearch() {
  if (!provider.value) {
    $q.notify({ type: 'warning', message: 'Please select a provider.' })
    return
  }
  if (!date.value) {
    $q.notify({ type: 'warning', message: 'Please select an appointment date.' })
    return
  }

  isSearching.value = true
  // Simulate network delay, then return stub data
  setTimeout(() => {
    patientResults.value = buildStubPatients(provider.value, date.value)
    hasSearched.value = true
    isSearching.value = false
    if (!patientResults.value.length) {
      $q.notify({ type: 'info', message: 'No patients found for the selected provider and date.' })
    }
  }, 500)
}

function onReset() {
  provider.value = null
  date.value = new Date().toISOString().slice(0, 10)
  patientResults.value = []
  searchText.value = ''
  isSearching.value = false
  hasSearched.value = false
  filteredProviderOptions.value = [...providerOptions.value]
}

function onAIScribe(row) {
  try {
    localStorage.removeItem('ai_scribe_patient')
    sessionStorage.removeItem('ai_scribe_patient')
    localStorage.setItem('ai_scribe_patient', JSON.stringify({ ...row, provider_id: provider.value }))
    sessionStorage.setItem('ai_scribe_patient', JSON.stringify({ ...row, provider_id: provider.value }))
    // Save search state so we can restore when navigating back
    const searchState = { provider: provider.value, date: date.value, patientResults: patientResults.value, searchText: searchText.value }
    localStorage.setItem('md_checkout_search_state', JSON.stringify(searchState))
  } catch { /* ignore */ }
  router.push('/forms/ai-scribe')
}

onMounted(() => {
  // Restore search state if returning from AI Scribe page
  try {
    const stored = localStorage.getItem('md_checkout_search_state') || sessionStorage.getItem('md_checkout_search_state')
    if (stored) {
      const searchState = JSON.parse(stored)
      provider.value = searchState.provider
      date.value = searchState.date
      patientResults.value = searchState.patientResults || []
      searchText.value = searchState.searchText || ''
      hasSearched.value = patientResults.value.length > 0
      localStorage.removeItem('md_checkout_search_state')
      sessionStorage.removeItem('md_checkout_search_state')
    }
  } catch { /* ignore */ }
})
</script>
