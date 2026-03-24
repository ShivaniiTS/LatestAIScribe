<template>
  <q-page class="page-container">
    <div class="text-h4 q-mb-md">Encounter History</div>

    <q-table
      :rows="encounters"
      :columns="columns"
      row-key="encounter_id"
      :loading="loading"
      :filter="filter"
      :pagination="{ rowsPerPage: 15 }"
    >
      <template v-slot:top-right>
        <q-input dense debounce="300" v-model="filter" placeholder="Search...">
          <template v-slot:append><q-icon name="search" /></template>
        </q-input>
      </template>

      <template v-slot:body-cell-status="props">
        <q-td :props="props">
          <q-badge :color="statusColor(props.row.status)" :label="props.row.status" />
        </q-td>
      </template>

      <template v-slot:body-cell-actions="props">
        <q-td :props="props">
          <q-btn flat dense size="sm" color="primary" icon="visibility"
            :to="'/encounters/' + props.row.encounter_id" />
        </q-td>
      </template>
    </q-table>
  </q-page>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from 'boot/axios'

const encounters = ref([])
const loading = ref(false)
const filter = ref('')

const columns = [
  { name: 'encounter_id', label: 'Encounter ID', field: 'encounter_id', sortable: true, align: 'left' },
  { name: 'provider_id', label: 'Provider', field: 'provider_id', sortable: true, align: 'left' },
  { name: 'mode', label: 'Mode', field: 'mode', sortable: true, align: 'left' },
  { name: 'visit_type', label: 'Visit Type', field: 'visit_type', sortable: true, align: 'left' },
  { name: 'status', label: 'Status', field: 'status', sortable: true, align: 'left' },
  { name: 'created_at', label: 'Created', field: 'created_at', sortable: true, align: 'left' },
  { name: 'actions', label: '', field: 'actions', align: 'right' },
]

function statusColor (status) {
  const map = {
    pending: 'grey', processing: 'blue', complete: 'positive',
    approved: 'positive', error: 'negative',
    mt_review: 'warning', mt_assigned: 'orange', mt_corrected: 'teal',
  }
  return map[status] || 'grey'
}

async function fetchHistory () {
  loading.value = true
  try {
    const { data } = await api.get('/encounters')
    encounters.value = data
  } catch (e) {
    console.error('Failed to load history', e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchHistory)
</script>
