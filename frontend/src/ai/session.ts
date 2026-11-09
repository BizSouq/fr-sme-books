import { ref } from 'vue';
import { clearConversation, isAssistantOpen, loadHistory } from './store';

/**
 * Whether the AI Guard lets this user use the assistant, from the boot.
 * The server checks again on every call, so this only decides what shows.
 */
export const canUseAi = ref(false);
export const isAiAdmin = ref(false);

export function initializeAiSession() {
  const ai = window.frappe.boot?.books?.ai;
  canUseAi.value = !!ai?.can_use;
  isAiAdmin.value = !!ai?.is_admin;
  loadHistory();
}

/** After the settings change who may use it. */
export function setAiAccess(canUse: boolean) {
  canUseAi.value = canUse;
  if (!canUse) {
    isAssistantOpen.value = false;
    clearConversation();
  }
}
