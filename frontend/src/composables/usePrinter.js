import { ref } from 'vue'

export function usePrinter() {
  return {
    printers: ref([]),
    selectedPrinter: ref(null),
    isLoadingPrinters: ref(false),
    printerError: ref(null),
    loadPrinters: async () => {},
    loadFromSession: () => {},
    saveSelectedPrinter: () => {},
    printDocument: async () => {},
  }
}
