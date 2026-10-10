/**
 * Cross-page data sync. Every page that lists data (Dashboard, Customers, Subscriptions,
 * Invoices, etc.) registers itself with onDataChanged(reload). After any create/update
 * action completes, a page calls promptForRefresh() instead of silently refreshing
 * everyone else — this shows a single confirmation banner (rendered once, in AppShell)
 * asking whether to update every other open page now. Only if the user says yes does
 * refreshAllData() actually run every registered page's reload function.
 */

type Listener = () => void;

const changeListeners = new Set<Listener>();
let promptListener: Listener | null = null;

export function onDataChanged(listener: Listener): () => void {
  changeListeners.add(listener);
  return () => {
    changeListeners.delete(listener);
  };
}

export function refreshAllData(): void {
  changeListeners.forEach((listener) => listener());
}

export function registerRefreshPrompt(listener: Listener): () => void {
  promptListener = listener;
  return () => {
    if (promptListener === listener) promptListener = null;
  };
}

/** Called after a page finishes saving something the user entered. */
export function promptForRefresh(): void {
  promptListener?.();
}
