<template>
  <q-page class="page-container">
    <div class="text-h4 q-mb-md">Dashboard</div>

    <div class="row q-col-gutter-md q-mb-lg">
      <div class="col-12 col-sm-4">
        <q-card class="bg-primary text-white">
          <q-card-section>
            <div class="text-h6">{{ stats.total }}</div>
            <div class="text-caption">Total Encounters</div>
          </q-card-section>
        </q-card>
      </div>
      <div class="col-12 col-sm-4">
        <q-card class="bg-positive text-white">
          <q-card-section>
            <div class="text-h6">{{ stats.complete }}</div>
            <div class="text-caption">Completed</div>
          </q-card-section>
        </q-card>
      </div>
      <div class="col-12 col-sm-4">
        <q-card class="bg-warning text-dark">
          <q-card-section>
            <div class="text-h6">{{ stats.pending_review }}</div>
            <div class="text-caption">Pending MT Review</div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <q-card>
      <q-card-section>
        <div class="text-h6">Recent Encounters</div>
      </q-card-section>
      <q-table
        :rows="recent"
        :columns="columns"
        row-key="encounter_id"
        flat
        :loading="loading"
        :pagination="{ rowsPerPage: 10 }"
      >
        <template v-slot:body-cell-status="props">
          <q-td :props="props">
            <q-badge :color="statusColor(props.row.status)" :label="props.row.status" />
          </q-td>
        </template>
        <template v-slot:body-cell-actions="props">
          <q-td :props="props">
            <q-btn flat dense size="sm" color="primary" label="View"
              :to="'/encounters/' + props.row.encounter_id" />
          </q-td>
        </template>
      </q-table>
    </q-card>
  </q-page>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from 'boot/axios'

const encounters = ref([])
const loading = ref(false)

const columns = [
  { name: 'encounter_id', label: 'ID', field: 'encounter_id', sortable: true, align: 'left' },
  { name: 'provider_id', label: 'Provider', field: 'provider_id', sortable: true, align: 'left' },
  { name: 'mode', label: 'Mode', field: 'mode', sortable: true, align: 'left' },
  { name: 'status', label: 'Status', field: 'status', sortable: true, align: 'left' },
  { name: 'created_at', label: 'Created', field: 'created_at', sortable: true, align: 'left' },
  { name: 'actions', label: '', field: 'actions', align: 'right' },
]

const stats = computed(() => {
  const all = encounters.value
  return {
    total: all.length,
    complete: all.filter(e => e.status === 'complete' || e.status === 'approved').length,
    pending_review: all.filter(e => e.status === 'mt_review' || e.status === 'mt_assigned').length,
  }
})

const recent = computed(() => {
  return [...encounters.value]
    .sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
    .slice(0, 20)
})

function statusColor (status) {
  const map = {
    pending: 'grey', processing: 'blue', complete: 'positive',
    approved: 'positive', error: 'negative',
    mt_review: 'warning', mt_assigned: 'orange', mt_corrected: 'teal',
    edited: 'info',
  }
  return map[status] || 'grey'
}

async function fetchEncounters () {
  loading.value = true
  try {
    const { data } = await api.get('/encounters')
    encounters.value = data
  } catch (e) {
    console.error('Failed to load encounters', e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchEncounters)
</script>
