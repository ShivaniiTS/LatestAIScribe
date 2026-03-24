<template>
  <q-page class="page-container">
    <div class="row items-center q-mb-md">
      <div class="text-h4 col">Providers</div>
      <q-btn color="primary" icon="add" label="Add Provider" @click="showCreate = true" />
    </div>

    <q-table
      :rows="providers"
      :columns="columns"
      row-key="provider_id"
      :loading="loading"
      :pagination="{ rowsPerPage: 10 }"
    >
      <template v-slot:body-cell-actions="props">
        <q-td :props="props">
          <q-btn flat dense size="sm" color="negative" icon="delete"
            @click="deleteProvider(props.row.provider_id)" />
        </q-td>
      </template>
    </q-table>

    <!-- Create dialog -->
    <q-dialog v-model="showCreate">
      <q-card style="min-width: 400px;">
        <q-card-section>
          <div class="text-h6">New Provider</div>
        </q-card-section>
        <q-card-section>
          <q-input v-model="newProvider.provider_id" label="Provider ID" outlined class="q-mb-sm" />
          <q-input v-model="newProvider.name" label="Name" outlined class="q-mb-sm" />
          <q-select v-model="newProvider.specialty" :options="specialties" label="Specialty" outlined class="q-mb-sm" />
          <q-select v-model="newProvider.note_type" :options="noteTypes" label="Note Type" outlined />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" label="Create" @click="createProvider" :loading="creating" />
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
const providers = ref([])
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)

const specialties = ['general', 'orthopedic', 'neurology', 'cardiology', 'pain_management']
const noteTypes = ['soap', 'hp', 'progress']

const newProvider = ref({
  provider_id: '',
  name: '',
  specialty: 'general',
  note_type: 'soap',
})

const columns = [
  { name: 'provider_id', label: 'ID', field: 'provider_id', sortable: true, align: 'left' },
  { name: 'name', label: 'Name', field: 'name', sortable: true, align: 'left' },
  { name: 'specialty', label: 'Specialty', field: 'specialty', sortable: true, align: 'left' },
  { name: 'note_type', label: 'Note Type', field: 'note_type', align: 'left' },
  { name: 'actions', label: '', field: 'actions', align: 'right' },
]

async function fetchProviders () {
  loading.value = true
  try {
    const { data } = await api.get('/providers')
    providers.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error('Failed to load providers', e)
  } finally {
    loading.value = false
  }
}

async function createProvider () {
  creating.value = true
  try {
    await api.post('/providers', newProvider.value)
    showCreate.value = false
    newProvider.value = { provider_id: '', name: '', specialty: 'general', note_type: 'soap' }
    $q.notify({ type: 'positive', message: 'Provider created' })
    fetchProviders()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Failed to create provider' })
  } finally {
    creating.value = false
  }
}

async function deleteProvider (id) {
  $q.dialog({ title: 'Delete Provider', message: `Delete provider ${id}?`, cancel: true })
    .onOk(async () => {
      try {
        await api.delete(`/providers/${id}`)
        $q.notify({ type: 'positive', message: 'Provider deleted' })
        fetchProviders()
      } catch (e) {
        $q.notify({ type: 'negative', message: 'Failed to delete provider' })
      }
    })
}

onMounted(fetchProviders)
</script>
