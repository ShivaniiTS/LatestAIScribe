<template>
  <q-page class="q-pa-xl bg-white text-black">
    <div class="max-width-page q-mx-auto q-px-lg q-pb-xl">
      <div class="row items-start q-mb-lg">
        <div class="col-12 col-md-8 text-center">
          <div class="row">
            <div class="text-h4 text-primary text-weight-bold">
              AI Scribe
            </div>
          </div>
        </div>
        <div class="col-12 col-md-4 text-right column items-end q-gutter-sm">
          <q-img
            src="/images/excelsia-logo.png"
            alt="Excelsia Injury Care"
            class="logo"
            ratio="4/1"
            loading="eager"
          />
        </div>
      </div>

      <!-- Provider Information Section -->
      <div class="row q-col-gutter-md q-mb-xl">
        <div class="col-12 col-md-6">
          <div class="text-caption text-weight-medium q-mb-xs">Supervising Provider:</div>
          <div class="text-body2 q-mb-md">{{ safeField('provider_name') || 'Not Selected' }}</div>

          <q-select
            v-model="formData.rendering_provider_id"
            :options="renderingProviderOptions"
            label="Rendering Provider"
            dense
            outlined
            emit-value
            map-options
            option-label="label"
            option-value="value"
            clearable
            use-input
            input-debounce="300"
            @filter="filterRenderingProviders"
            fill-input
            hide-selected
            style="width: 90%"
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

        <div class="col-12 col-md-6 column text-right text-caption">
          <div>
            <span class="text-weight-bold">Date of Service:</span> {{ formatDate(formData.date) || placeholderDate }}
          </div>
          <div>
            <span class="text-weight-bold">Location:</span> {{ safeField('location_name') }}
          </div>
          <div><span class="text-weight-bold">Name:</span> {{ safeField('patient_name') }}</div>
          <div>
            <span class="text-weight-bold">Account Number:</span> {{ safeField('account_number') }}
          </div>
          <div>
            <span class="text-weight-bold">Guarantor:</span> {{ safeField('guarantor_id') }}
          </div>
          <div>
            <span class="text-weight-bold">Provider:</span> {{ safeField('provider_name') }}
          </div>
          <div><span class="text-weight-bold">Case:</span> {{ safeField('case_name') }}</div>
          <div><span class="text-weight-bold">Date of Birth:</span> {{ formatDate(formData.d_o_b) || 'N/A' }}</div>
        </div>
      </div>

      <!-- AI Scribe Audio Recorder -->
      <AIScribeAudioRecorder 
        :form-data="formData"
        @recording-submitted="onRecordingSubmitted"
        @recording-discarded="onRecordingDiscarded"
      />
    </div>
  </q-page>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { api } from 'boot/axios'
import AIScribeAudioRecorder from 'src/ai_scribe_frontend/components/AIScribeAudioRecorder.vue'

// Provider options for rendering provider dropdown - static list (same as MDCheckoutFormPage)
const renderingProviderOptions = ref([
  { label: 'Caleb Ademiloye, NP', value: 'Caleb Ademiloye, NP' },
  { label: 'Jebeh Baimba, NP', value: 'Jebeh Baimba, NP' },
  { label: 'Fese Bokosah, NP', value: 'Fese Bokosah, NP' },
  { label: 'Irine Breslaw, PA', value: 'Irine Breslaw, PA' },
  { label: 'Tiffany Halliburton, NP', value: 'Tiffany Halliburton, NP' },
  { label: 'Mariama Koroma, NP', value: 'Mariama Koroma, NP' },
  { label: 'Antonina Mudimba, NP', value: 'Antonina Mudimba, NP' },
  { label: 'Paul Peace, NP', value: 'Paul Peace, NP' },
  { label: 'Lourdes Rivera, NP', value: 'Lourdes Rivera, NP' },
  { label: 'Dan Schechter, PA', value: 'Dan Schechter, PA' },
  { label: 'Rajul Shah, PA', value: 'Rajul Shah, PA' },
])
const allRenderingProviders = ref([
  { label: 'Caleb Ademiloye, NP', value: 'Caleb Ademiloye, NP' },
  { label: 'Jebeh Baimba, NP', value: 'Jebeh Baimba, NP' },
  { label: 'Fese Bokosah, NP', value: 'Fese Bokosah, NP' },
  { label: 'Irine Breslaw, PA', value: 'Irine Breslaw, PA' },
  { label: 'Tiffany Halliburton, NP', value: 'Tiffany Halliburton, NP' },
  { label: 'Mariama Koroma, NP', value: 'Mariama Koroma, NP' },
  { label: 'Antonina Mudimba, NP', value: 'Antonina Mudimba, NP' },
  { label: 'Paul Peace, NP', value: 'Paul Peace, NP' },
  { label: 'Lourdes Rivera, NP', value: 'Lourdes Rivera, NP' },
  { label: 'Dan Schechter, PA', value: 'Dan Schechter, PA' },
  { label: 'Rajul Shah, PA', value: 'Rajul Shah, PA' },
])

// Reactive form data - limited demographic fields only
const formData = reactive({
  date: '',
  patient_name: '',
  account_number: '',
  case_name: '',
  case_number: '',
  location_code: '',
  location_name: '',
  provider_name: '',
  provider_id: null,
  rendering_provider_id: null,
  guarantor_id: '',
  d_o_b: '',
  num_pt_visits: 0,
  injury_date: '',
  case_desc: '',
  cost_center_desc: '',
  primary_carrier: '',
  appointment_id: null,
  encounter_id: null,
})

// Placeholder date for display when no date is set
const placeholderDate = computed(() => {
  return new Date().toLocaleDateString('en-US', {
    month: 'numeric',
    day: 'numeric',
    year: 'numeric',
  })
})

// Watch for rendering provider changes and log updated demographic data
watch(() => formData.rendering_provider_id, (newValue) => {
  if (newValue) {
    const demographicData = {
      date: formatDate(formData.date) || formData.date,
      patient_name: formData.patient_name,
      account_number: formData.account_number,
      case_name: formData.case_name,
      case_number: formData.case_number,
      location_code: formData.location_code,
      location_name: formData.location_name,
      provider_name: formData.provider_name,
      provider_id: formData.provider_id,
      rendering_provider: newValue,
      guarantor_id: formData.guarantor_id,
      d_o_b: formatDate(formData.d_o_b) || formData.d_o_b,
      num_pt_visits: formData.num_pt_visits,
      injury_date: formatDate(formData.injury_date) || formData.injury_date,
      case_desc: formData.case_desc,
      cost_center_desc: formData.cost_center_desc,
      primary_carrier: formData.primary_carrier,
      appointment_id: formData.appointment_id,
      encounter_id: formData.encounter_id
    }
    console.log('=== AI Scribe: Updated Demographic Data (Rendering Provider Selected) ===')
    console.log(JSON.stringify(demographicData, null, 2))
  }
})

// Safe field accessor
function safeField(fieldName) {
  const value = formData[fieldName]
  if (value === null || value === undefined || value === '') {
    return 'N/A'
  }
  return String(value).trim() || 'N/A'
}

// Format date to M/D/YYYY format
function formatDate(dateStr) {
  if (!dateStr) return null
  
  try {
    // Handle various date formats
    let date
    
    // Check if it's already in M/D/YYYY or MM/DD/YYYY format
    if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(dateStr)) {
      return dateStr
    }
    
    // Check if it's in YYYY-MM-DD format (with optional time)
    if (/^\d{4}-\d{2}-\d{2}/.test(dateStr)) {
      const parts = dateStr.split('T')[0].split('-')
      const month = parseInt(parts[1], 10)
      const day = parseInt(parts[2], 10)
      const year = parts[0]
      return `${month}/${day}/${year}`
    }
    
    // Try parsing as a Date object
    date = new Date(dateStr)
    if (!isNaN(date.getTime())) {
      const month = date.getMonth() + 1
      const day = date.getDate()
      const year = date.getFullYear()
      return `${month}/${day}/${year}`
    }
    
    return dateStr
  } catch {
    return dateStr
  }
}

// Filter function for rendering provider dropdown
function filterRenderingProviders(val, update) {
  update(() => {
    if (val === '') {
      renderingProviderOptions.value = allRenderingProviders.value
    } else {
      const needle = val.toLowerCase()
      renderingProviderOptions.value = allRenderingProviders.value.filter(
        (provider) => provider.label.toLowerCase().indexOf(needle) > -1,
      )
    }
  })
}

// Load patient demographic data on mount
onMounted(async () => {
  await loadPatientData()
})

// Flag to prevent duplicate console logs
let hasLoggedData = false

async function loadPatientData() {
  try {
    // Prefer localStorage (new behavior), fallback to sessionStorage for backwards compatibility
    const stored =
      localStorage.getItem('ai_scribe_patient') ||
      sessionStorage.getItem('ai_scribe_patient')
    
    if (stored) {
      const patientData = JSON.parse(stored)
      
      // Load basic demographic fields from storage first
      formData.date = patientData.date || patientData.appointment_date || ''
      formData.patient_name = patientData.patient_name || patientData.patient_full_name || ''
      formData.account_number = patientData.account_number || ''
      formData.case_name = patientData.case_name || ''
      formData.case_number = patientData.case_number || ''
      formData.location_code = patientData.location_code || ''
      formData.location_name = patientData.location_name || ''
      formData.provider_name = patientData.provider_name || ''
      formData.provider_id = patientData.provider_id || null
      formData.rendering_provider_id = patientData.rendering_provider_id || null
      formData.guarantor_id = patientData.guarantor_id || ''
      formData.d_o_b = patientData.d_o_b || patientData.date_of_birth || ''
      formData.num_pt_visits = patientData.num_pt_visits || patientData.pt_visit_count || 0
      formData.injury_date = patientData.injury_date || ''
      formData.case_desc = patientData.case_desc || ''
      formData.cost_center_desc = patientData.cost_center_desc || ''
      formData.primary_carrier = patientData.primary_carrier || ''
      formData.appointment_id = patientData.appointment_id || null
      formData.encounter_id = patientData.encounter_id || null
      
      // Always fetch complete patient data from API when appointment_id is available
      // This ensures all fields (injury_date, case_desc, cost_center_desc, primary_carrier, encounter_id) are populated
      if (patientData.appointment_id) {
        await loadPatientFromAppointment(patientData.appointment_id)
      }
      
      // Log only essential demographic data once
      if (!hasLoggedData) {
        hasLoggedData = true
        const demographicData = {
          date: formatDate(formData.date) || formData.date,
          patient_name: formData.patient_name,
          account_number: formData.account_number,
          case_name: formData.case_name,
          case_number: formData.case_number,
          location_code: formData.location_code,
          location_name: formData.location_name,
          provider_name: formData.provider_name,
          provider_id: formData.provider_id,
          rendering_provider: formData.rendering_provider_id,
          guarantor_id: formData.guarantor_id,
          d_o_b: formatDate(formData.d_o_b) || formData.d_o_b,
          num_pt_visits: formData.num_pt_visits,
          injury_date: formatDate(formData.injury_date) || formData.injury_date,
          case_desc: formData.case_desc,
          cost_center_desc: formData.cost_center_desc,
          primary_carrier: formData.primary_carrier,
          appointment_id: formData.appointment_id,
          encounter_id: formData.encounter_id
        }
        console.log('=== AI Scribe: Patient Demographic Data ===')
        console.log(JSON.stringify(demographicData, null, 2))
      }
    }
  } catch (error) {
    console.error('Error loading patient data:', error)
  }
}

// Load complete patient data from API using appointment ID
async function loadPatientFromAppointment(appointmentId) {
  try {
    console.log(`Fetching patient data for appointment_id: ${appointmentId}`)
    
    const response = await api.get(`/patients/appointment/${appointmentId}`)
    const patient = response.data
    
    // Update form with complete patient data
    formData.patient_name = patient.patient_full_name || patient.patient_name || formData.patient_name
    formData.account_number = patient.account_number || formData.account_number
    formData.case_name = patient.case_name || formData.case_name
    formData.case_number = patient.case_number || formData.case_number
    formData.location_code = patient.location_code || formData.location_code
    formData.location_name = patient.location_name || formData.location_name
    formData.provider_name = patient.provider_name || formData.provider_name
    formData.provider_id = patient.provider_id || formData.provider_id
    formData.guarantor_id = patient.guarantor_id || formData.guarantor_id
    formData.num_pt_visits = patient.pt_visit_count ?? patient.visit_count ?? formData.num_pt_visits
    formData.injury_date = patient.injury_date || formData.injury_date
    formData.case_desc = patient.case_desc || formData.case_desc
    formData.cost_center_desc = patient.cost_center_desc || formData.cost_center_desc
    formData.primary_carrier = patient.primary_carrier || formData.primary_carrier
    formData.encounter_id = patient.encounter_id || formData.encounter_id
    
    // Format the date of birth
    let dateOfBirth = patient.date_of_birth || ''
    if (dateOfBirth) {
      formData.d_o_b = dateOfBirth
    }
    
    // Format the appointment date
    let appointmentDate = patient.appointment_date || ''
    if (appointmentDate && !formData.date) {
      formData.date = appointmentDate
    }
    
  } catch (error) {
    console.error('Failed to load patient data from API:', error)
    // Silently fail - use whatever data we have from storage
  }
}

// Event handlers for audio recorder
function onRecordingSubmitted(data) {
  console.log('Recording submitted:', data)
}

function onRecordingDiscarded() {
  console.log('Recording discarded')
}
</script>

<style scoped>
.max-width-page {
  max-width: 1200px;
}

.logo {
  width: 180px;
  max-width: 100%;
}

.section-card {
  background: #fafafa;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: #1976d2;
  margin-bottom: 12px;
  border-bottom: 2px solid #1976d2;
  padding-bottom: 4px;
}
</style>
