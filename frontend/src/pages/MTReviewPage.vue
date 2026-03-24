<template>
  <q-page class="page-container">
    <div class="text-h4 q-mb-md">MT Review Queue</div>

    <q-table
      :rows="queue"
      :columns="columns"
      row-key="encounter_id"
      :loading="loading"
      :pagination="{ rowsPerPage: 10 }"
    >
      <template v-slot:body-cell-status="props">
        <q-td :props="props">
          <q-badge :color="props.row.status === 'mt_assigned' ? 'orange' : 'warning'" :label="props.row.status" />
        </q-td>
      </template>

      <template v-slot:body-cell-actions="props">
        <q-td :props="props">
          <q-btn flat dense size="sm" color="primary" label="Review"
            @click="openReview(props.row)" />
        </q-td>
      </template>
    </q-table>

    <!-- Review dialog -->
    <q-dialog v-model="reviewDialog" maximized>
      <q-card>
        <q-card-section class="row items-center q-pb-none">
          <div class="text-h6">Review: {{ currentReview.encounter_id }}</div>
          <q-space />
          <q-btn flat round dense icon="close" v-close-popup />
        </q-card-section>

        <q-card-section class="row q-col-gutter-md" style="height: calc(100vh - 150px); overflow: auto;">
          <div class="col-12 col-md-6">
            <div class="text-subtitle2 q-mb-sm">Transcript</div>
            <div style="white-space: pre-wrap; font-family: monospace; font-size: 13px; background: #f5f5f5; padding: 12px; border-radius: 8px; max-height: 80vh; overflow: auto;">
              {{ currentReview.transcript }}
            </div>
          </div>
          <div class="col-12 col-md-6">
            <div class="text-subtitle2 q-mb-sm">Clinical Note (editable)</div>
            <q-input v-model="correctedContent" type="textarea" outlined :rows="25" />
            <q-input v-model="reviewComments" label="Comments" outlined class="q-mt-sm" />
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" label="Submit Correction" @click="submitCorrection" :loading="submitting" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from 'boot/axios'
import { useQuasar } from 'quasar'

const $q = useQuasar()
const queue = ref([])
const loading = ref(false)
const reviewDialog = ref(false)
const currentReview = ref({})
const correctedContent = ref('')
const reviewComments = ref('')
const submitting = ref(false)

const columns = [
  { name: 'encounter_id', label: 'Encounter', field: 'encounter_id', sortable: true, align: 'left' },
  { name: 'provider_id', label: 'Provider', field: 'provider_id', sortable: true, align: 'left' },
  { name: 'mode', label: 'Mode', field: 'mode', align: 'left' },
  { name: 'status', label: 'Status', field: 'status', sortable: true, align: 'left' },
  { name: 'actions', label: '', field: 'actions', align: 'right' },
]

async function fetchQueue () {
  loading.value = true
  try {
    const { data } = await api.get('/mt/queue')
    queue.value = data
  } catch (e) {
    console.error('Failed to load MT queue', e)
  } finally {
    loading.value = false
  }
}

async function openReview (enc) {
  try {
    const { data } = await api.get(`/mt/${enc.encounter_id}`)
    currentReview.value = data
    correctedContent.value = data.note_content || ''
    reviewComments.value = ''
    reviewDialog.value = true
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Failed to load review details' })
  }
}

async function submitCorrection () {
  submitting.value = true
  try {
    await api.post(`/mt/${currentReview.value.encounter_id}/submit`, {
      reviewer_id: 'mt_reviewer',
      corrected_content: correctedContent.value,
      comments: reviewComments.value,
    })
    reviewDialog.value = false
    $q.notify({ type: 'positive', message: 'Correction submitted' })
    fetchQueue()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Submission failed' })
  } finally {
    submitting.value = false
  }
}

onMounted(fetchQueue)
</script>
