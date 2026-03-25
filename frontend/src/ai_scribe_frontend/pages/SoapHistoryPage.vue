<template>
  <q-page class="q-pa-md soap-history-page">
    <q-card flat bordered class="rounded-borders">
      <!-- Header -->
      <q-card-section class="header-section">
        <div class="row items-center justify-between">
          <div class="row items-center q-gutter-sm">
            <q-icon name="schedule" size="28px" color="primary" />
            <span class="text-h5 text-weight-bold">AI Scribe History</span>
          </div>
          <div class="row items-center q-gutter-md">
            <q-input v-model="searchTerm" placeholder="Search patients..." outlined dense class="search-input">
              <template v-slot:prepend>
                <q-icon name="search" color="grey-6" />
              </template>
            </q-input>
            <q-btn round flat color="secondary" icon="refresh" @click="fetchHistoryData" :loading="loading">
              <q-tooltip>Refresh</q-tooltip>
            </q-btn>
          </div>
        </div>
      </q-card-section>

      <q-card-section class="q-pa-sm bg-grey-1 row items-center justify-between">
        <div class="text-caption text-grey-7">
          <q-icon name="schedule" size="xs" class="q-mr-xs" />
          Last updated: {{ lastPollTime || 'Never' }}
        </div>
        <div class="text-caption text-grey-7">
          <q-icon name="folder" size="xs" class="q-mr-xs" />
          {{ encounters.length }} records
        </div>
      </q-card-section>

      <!-- Main Table -->
      <q-card-section class="q-pa-none">
        <div v-if="loading && encounters.length === 0" class="text-center q-pa-xl">
          <q-spinner-dots size="60px" color="primary" />
          <div class="q-mt-md text-grey-6">Loading history...</div>
        </div>

        <div v-else-if="filteredEncounters.length === 0" class="text-center q-pa-xl">
          <q-icon name="inbox" size="80px" color="grey-5" />
          <div class="q-mt-md text-h6 text-grey-6">No Records Found</div>
          <div class="text-body2 text-grey-5 q-mt-sm">
            {{ searchTerm ? 'No matching records' : 'Submit an AI Scribe recording to see results here.' }}
          </div>
        </div>

        <q-table
          v-else
          :rows="filteredEncounters"
          :columns="columns"
          row-key="encounter_id"
          flat
          :pagination="pagination"
          class="soap-history-table"
        >
          <template v-slot:body-cell-patient="props">
            <q-td :props="props"><span class="text-weight-medium">{{ props.row.patient_name || props.row.encounter_id }}</span></q-td>
          </template>
          <template v-slot:body-cell-appointment="props">
            <q-td :props="props">{{ props.row.appointment_date || props.row.date || '—' }}</q-td>
          </template>
          <template v-slot:body-cell-provider="props">
            <q-td :props="props">{{ props.row.provider_name || props.row.provider_id || '—' }}</q-td>
          </template>
          <template v-slot:body-cell-audio="props">
            <q-td :props="props" class="text-center">
              <q-btn
                v-if="props.row.has_audio"
                round flat color="primary" icon="play_arrow" size="sm"
                @click="playAudio(props.row)"
              >
                <q-tooltip>Play Recording</q-tooltip>
              </q-btn>
              <span v-else class="text-grey-5">—</span>
            </q-td>
          </template>
          <template v-slot:body-cell-soap="props">
            <q-td :props="props" class="text-center">
              <q-btn
                v-if="props.row.soap_note"
                round flat color="primary" icon="description" size="sm"
                @click="showSoapDialog(props.row)"
              >
                <q-tooltip>View SOAP Note</q-tooltip>
              </q-btn>
              <span v-else class="text-grey-5">—</span>
            </q-td>
          </template>
          <template v-slot:body-cell-status="props">
            <q-td :props="props" class="text-center">
              <q-chip :color="getStatusColor(props.row.status)" text-color="white" size="sm">
                {{ props.row.status || 'Processing' }}
              </q-chip>
            </q-td>
          </template>
        </q-table>
      </q-card-section>
    </q-card>

    <!-- Audio Player Dialog -->
    <q-dialog v-model="audioDialogVisible">
      <q-card style="min-width: 350px">
        <q-card-section class="row items-center q-pb-none">
          <div class="text-h6">Audio Playback</div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-card-section>
          <audio ref="audioPlayerEl" controls style="width: 100%">
            <source :src="currentAudioUrl" />
            Your browser does not support the audio element.
          </audio>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- SOAP Note Dialog -->
    <q-dialog v-model="soapDialogVisible" maximized>
      <q-card>
        <q-card-section class="row items-center bg-primary text-white q-py-md">
          <q-icon name="description" size="md" class="q-mr-sm" />
          <div class="text-h6">SOAP Note - {{ currentEncounterId }}</div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup color="white" />
        </q-card-section>
        <q-card-section class="q-pa-lg" style="max-height: 80vh; overflow-y: auto;">
          <div v-if="currentSoapNote" class="soap-content">
            <div v-for="key in Object.keys(currentSoapNote)" :key="key" class="q-mb-lg">
              <div class="text-h6 text-weight-bold text-uppercase q-mb-sm text-primary">
                {{ key.replace(/_/g, ' ') }}
              </div>
              <div class="soap-text">{{ currentSoapNote[key] || 'No data available' }}</div>
            </div>
          </div>
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from 'boot/axios'

const encounters = ref([])
const loading = ref(false)
const searchTerm = ref('')
const lastPollTime = ref(null)

const audioDialogVisible = ref(false)
const soapDialogVisible = ref(false)
const currentAudioUrl = ref('')
const currentSoapNote = ref(null)
const currentEncounterId = ref('')

const pagination = ref({ sortBy: 'date', descending: true, page: 1, rowsPerPage: 25 })

const columns = [
  { name: 'patient', label: 'Patient', field: 'patient_name', align: 'left', sortable: true },
  { name: 'appointment', label: 'Appointment', field: 'appointment_date', align: 'left', sortable: true },
  { name: 'provider', label: 'Provider', field: 'provider_name', align: 'left', sortable: true },
  { name: 'audio', label: 'Recording', field: 'has_audio', align: 'center' },
  { name: 'soap', label: 'SOAP', field: 'soap_note', align: 'center' },
  { name: 'status', label: 'Status', field: 'status', align: 'center' },
]

const filteredEncounters = computed(() => {
  if (!searchTerm.value) return encounters.value
  const term = searchTerm.value.toLowerCase()
  return encounters.value.filter(enc =>
    (enc.patient_name || '').toLowerCase().includes(term) ||
    (enc.provider_name || '').toLowerCase().includes(term) ||
    (enc.encounter_id || '').toLowerCase().includes(term),
  )
})

function getStatusColor(status) {
  const map = {
    completed: 'positive',
    processing: 'primary',
    error: 'negative',
    failed: 'negative',
    pending: 'grey-6',
  }
  return map[(status || '').toLowerCase()] || 'grey-6'
}

async function fetchHistoryData() {
  loading.value = true
  try {
    const resp = await api.get('/api/soap-history')
    encounters.value = Array.isArray(resp.data) ? resp.data : (resp.data.encounters || [])
    lastPollTime.value = new Date().toLocaleTimeString()
  } catch (err) {
    console.error('Failed to load history:', err)
    encounters.value = []
  } finally {
    loading.value = false
  }
}

function playAudio(row) {
  currentAudioUrl.value = `/api/audio/${row.encounter_id}`
  audioDialogVisible.value = true
}

function showSoapDialog(row) {
  currentEncounterId.value = row.encounter_id
  try {
    currentSoapNote.value = typeof row.soap_note === 'string'
      ? JSON.parse(row.soap_note)
      : row.soap_note
  } catch {
    currentSoapNote.value = { 'Note': row.soap_note }
  }
  soapDialogVisible.value = true
}

let pollingTimer = null
onMounted(() => {
  fetchHistoryData()
  pollingTimer = setInterval(fetchHistoryData, 60000) // refresh every minute
})
onUnmounted(() => { if (pollingTimer) clearInterval(pollingTimer) })
</script>

<style scoped>
.soap-text {
  white-space: pre-wrap;
  font-family: Georgia, serif;
  line-height: 1.6;
}
.search-input {
  min-width: 220px;
}
</style>
