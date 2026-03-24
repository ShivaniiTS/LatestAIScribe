<template>
  <q-page class="page-container">
    <q-btn flat icon="arrow_back" label="Back" class="q-mb-md" @click="$router.back()" />

    <div v-if="loading" class="text-center q-pa-xl">
      <q-spinner-dots size="48px" color="primary" />
    </div>

    <div v-else-if="error" class="text-center q-pa-xl">
      <q-icon name="error" size="48px" color="negative" />
      <div class="text-h6 q-mt-md">{{ error }}</div>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="row items-center q-mb-md">
        <div class="col">
          <div class="text-h5">Encounter {{ encounter.encounter_id }}</div>
          <div class="text-body2 text-grey-7">
            Provider: {{ encounter.provider_id }} &bull;
            Mode: {{ encounter.mode }} &bull;
            <q-badge :color="statusColor(encounter.status)" :label="encounter.status" />
          </div>
        </div>
        <div class="col-auto">
          <q-btn color="primary" icon="edit" label="Edit Note" @click="editMode = !editMode"
            v-if="note && !editMode" />
          <q-btn color="positive" icon="check" label="Approve" @click="approveNote"
            v-if="note && encounter.status !== 'approved'" class="q-ml-sm" />
        </div>
      </div>

      <!-- Audio player -->
      <q-card class="q-mb-md" v-if="hasAudio">
        <q-card-section>
          <div class="text-subtitle2 q-mb-sm">Audio Recording</div>
          <audio controls :src="audioUrl" style="width: 100%"></audio>
        </q-card-section>
      </q-card>

      <!-- Clinical note -->
      <q-card class="q-mb-md" v-if="note">
        <q-card-section>
          <div class="text-h6 q-mb-sm">Clinical Note</div>
          <q-input v-if="editMode" v-model="editContent" type="textarea" outlined
            :rows="20" class="q-mb-sm" />
          <div v-else class="note-content" v-html="renderMarkdown(note)" />
        </q-card-section>
        <q-card-actions align="right" v-if="editMode">
          <q-btn flat label="Cancel" @click="editMode = false" />
          <q-btn color="primary" label="Save" @click="saveNote" :loading="saving" />
        </q-card-actions>
      </q-card>

      <!-- Transcript -->
      <q-card v-if="transcript">
        <q-card-section>
          <q-expansion-item label="Transcript" icon="subtitles" default-closed>
            <div class="q-pa-md" style="white-space: pre-wrap; font-family: monospace; font-size: 13px;">{{ transcript }}</div>
          </q-expansion-item>
        </q-card-section>
      </q-card>
    </template>
  </q-page>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api } from 'boot/axios'
import { useQuasar } from 'quasar'

const $q = useQuasar()
const route = useRoute()

const encounter = ref({})
const note = ref('')
const transcript = ref('')
const loading = ref(true)
const error = ref(null)
const editMode = ref(false)
const editContent = ref('')
const saving = ref(false)
const hasAudio = ref(false)

const audioUrl = computed(() => {
  const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  return `${base}/encounters/${route.params.id}/audio`
})

function statusColor (status) {
  const map = {
    pending: 'grey', processing: 'blue', complete: 'positive',
    approved: 'positive', error: 'negative',
    mt_review: 'warning', mt_assigned: 'orange', edited: 'info',
  }
  return map[status] || 'grey'
}

function renderMarkdown (text) {
  // Simple markdown rendering for clinical notes
  return text
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

async function fetchData () {
  loading.value = true
  try {
    const { data: enc } = await api.get(`/encounters/${route.params.id}`)
    encounter.value = enc

    try {
      const { data: noteData } = await api.get(`/encounters/${route.params.id}/note`)
      note.value = noteData.content
      editContent.value = noteData.content
    } catch { /* no note yet */ }

    try {
      const { data: txData } = await api.get(`/encounters/${route.params.id}/transcript`)
      transcript.value = txData.content
    } catch { /* no transcript yet */ }

    try {
      await api.head(`/encounters/${route.params.id}/audio`)
      hasAudio.value = true
    } catch { hasAudio.value = false }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Encounter not found'
  } finally {
    loading.value = false
  }
}

async function saveNote () {
  saving.value = true
  try {
    await api.put(`/notes/${route.params.id}`, { content: editContent.value })
    note.value = editContent.value
    editMode.value = false
    $q.notify({ type: 'positive', message: 'Note saved' })
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Failed to save note' })
  } finally {
    saving.value = false
  }
}

async function approveNote () {
  try {
    await api.post(`/notes/${route.params.id}/approve`, { approved_by: 'provider' })
    encounter.value.status = 'approved'
    $q.notify({ type: 'positive', message: 'Note approved' })
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Failed to approve note' })
  }
}

onMounted(fetchData)
</script>

<style scoped>
.note-content {
  line-height: 1.6;
}
.note-content h2, .note-content h3 {
  margin-top: 16px;
  margin-bottom: 8px;
}
</style>
