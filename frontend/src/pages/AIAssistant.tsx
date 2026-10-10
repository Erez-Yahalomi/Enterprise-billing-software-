import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  MenuItem,
  Paper,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { onDataChanged, promptForRefresh } from "../api/dataSync";
import type { ApprovalRequest, ChatResponse, Customer, Invoice, PricePlan, Subscription } from "../api/types";

interface Message {
  role: "user" | "assistant";
  text: string;
  toolCalls?: { tool: string; status: string }[];
  verdict?: Verdict;
}

// Real-time verification of each reply: which engine wrote it and whether the question was answered.
interface Verdict {
  severity: "success" | "info" | "warning";
  label: string;
}

function verdictFor(r: ChatResponse): Verdict {
  if (r.answer_status === "not_understood") return { severity: "warning", label: "Not answered — I could not match that to your data" };
  if (r.answer_status === "needs_info") return { severity: "warning", label: "Not answered yet — more detail needed" };
  if (r.answered_by === "gemini") return { severity: "success", label: "Answered by the Gemini AI model" };
  if (r.answered_by === "ollama") return { severity: "success", label: "Answered by the local AI model" };
  return { severity: "info", label: "Answered from your data by the built-in engine (AI model unavailable right now)" };
}

// Keep the conversation for as long as the user stays on this page. It lives in sessionStorage so it
// survives re-renders, remounts and page reloads, and is cleared only when the user navigates to a
// different page (see the cleanup effect in the component).
const CHAT_STORAGE_KEY = "ai-assistant-messages";

function loadSavedMessages(): Message[] {
  try {
    const raw = sessionStorage.getItem(CHAT_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Message[]) : [];
  } catch {
    return [];
  }
}

function saveMessages(messages: Message[]) {
  try {
    sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
  } catch {
    // storage unavailable (private mode / quota) - the chat still works, it just isn't persisted
  }
}

const PROTECTED_ACTIONS = [
  { value: "pause_subscription", label: "Pause a subscription" },
  { value: "reactivate_subscription", label: "Reactivate a paused subscription" },
  { value: "change_subscription_plan", label: "Change a subscription's plan" },
];

// Tools that actually change business data when they execute immediately (Tier B).
// Tier A lookups never mutate anything, so they don't need a refresh prompt.
const MUTATING_TOOLS = new Set(["create_support_case", "update_customer_contact_details", "generate_invoice"]);

export default function AIAssistant() {
  const [params] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>(loadSavedMessages);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [notice, setNotice] = useState<Verdict | null>(null);

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [plans, setPlans] = useState<PricePlan[]>([]);

  // Quick action form state
  const [lookupType, setLookupType] = useState<"customer" | "subscription" | "invoice">("customer");
  const [lookupId, setLookupId] = useState("");

  const [caseCustomerId, setCaseCustomerId] = useState("");
  const [caseSubject, setCaseSubject] = useState("");

  const [contactCustomerId, setContactCustomerId] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactCountry, setContactCountry] = useState("");

  const [protectedAction, setProtectedAction] = useState(PROTECTED_ACTIONS[0].value);
  const [protectedSubscriptionId, setProtectedSubscriptionId] = useState("");
  const [protectedNewPlanId, setProtectedNewPlanId] = useState("");

  const context = {
    customer_id: params.get("customer_id") || undefined,
    subscription_id: params.get("subscription_id") || undefined,
    invoice_id: params.get("invoice_id") || undefined,
  };

  // Save every change to the conversation.
  useEffect(() => {
    saveMessages(messages);
  }, [messages]);

  // Clear the saved conversation only when the user really leaves this page (the URL has changed
  // by the time this cleanup runs). A re-render, remount or reload on /ai keeps it.
  useEffect(() => {
    return () => {
      if (window.location.pathname !== "/ai") {
        try {
          sessionStorage.removeItem(CHAT_STORAGE_KEY);
        } catch {
          // ignore
        }
      }
    };
  }, []);

  const loadApprovals = () => api.get<ApprovalRequest[]>("/ai/approvals").then(setApprovals);

  useEffect(() => {
    const loadReferenceData = () => {
      api.get<Customer[]>("/customers").then(setCustomers);
      api.get<Subscription[]>("/subscriptions").then(setSubscriptions);
      api.get<Invoice[]>("/invoices").then(setInvoices);
      api.get<PricePlan[]>("/price-plans").then(setPlans);
    };
    loadApprovals();
    loadReferenceData();
    return onDataChanged(() => {
      loadApprovals();
      loadReferenceData();
    });
  }, []);

  const customerName = (id: string) => customers.find((c) => c.id === id)?.name ?? id;

  const send = async () => {
    if (!input.trim()) return;
    const question = input;
    setMessages((m) => [...m, { role: "user", text: question }]);
    setInput("");
    setSending(true);
    try {
      const response = await api.post<ChatResponse>("/ai/chat", { message: question, context });
      const verdict = verdictFor(response);
      setNotice(verdict);
      setMessages((m) => [...m, { role: "assistant", text: response.reply, toolCalls: response.tool_calls, verdict }]);
      if (response.pending_approval_id) loadApprovals();
      if (response.tool_calls.some((tc) => tc.status === "executed" && MUTATING_TOOLS.has(tc.tool))) promptForRefresh();
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: e instanceof Error ? e.message : "The request failed or timed out. Please try again." },
      ]);
    } finally {
      setSending(false);
    }
  };

  const resolve = async (id: string, action: "approve" | "reject") => {
    await api.post(`/ai/approvals/${id}/${action}`);
    loadApprovals();
    if (action === "approve") promptForRefresh();
  };

  // Quick actions call the same tool gateway the chat uses, directly — this guarantees
  // every tool the agent has is actually reachable from the UI, not just the ones the
  // free-text chat happens to recognize.
  const runTool = async (tool: string, parameters: Record<string, unknown>, userLabel: string) => {
    setMessages((m) => [...m, { role: "user", text: userLabel }]);
    setSending(true);
    try {
      const result = await api.post<{ status: string; data: unknown; approval_id: string | null }>(
        `/ai/tools/${tool}`,
        { parameters }
      );
      const reply =
        result.status === "pending_approval"
          ? "Submitted for approval — see Pending Approvals below."
          : `Done. ${JSON.stringify(result.data)}`;
      setMessages((m) => [...m, { role: "assistant", text: reply, toolCalls: [{ tool, status: result.status }] }]);
      if (result.status === "pending_approval") loadApprovals();
      if (result.status === "executed" && MUTATING_TOOLS.has(tool)) promptForRefresh();
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: e instanceof Error ? e.message : "That action failed." },
      ]);
    } finally {
      setSending(false);
    }
  };

  const runLookup = () => {
    if (!lookupId) return;
    const tool = lookupType === "customer" ? "get_customer" : lookupType === "subscription" ? "get_subscription" : "get_invoice";
    const paramKey = lookupType === "customer" ? "customer_id" : lookupType === "subscription" ? "subscription_id" : "invoice_id";
    runTool(tool, { [paramKey]: lookupId }, `Look up ${lookupType} ${lookupId}`);
  };

  const runCreateCase = () => {
    if (!caseCustomerId || !caseSubject) return;
    runTool(
      "create_support_case",
      { customer_id: caseCustomerId, subject: caseSubject },
      `Open a support case for ${customerName(caseCustomerId)}: "${caseSubject}"`
    );
    setCaseSubject("");
  };

  const runUpdateContact = () => {
    if (!contactCustomerId || (!contactEmail && !contactCountry)) return;
    runTool(
      "update_customer_contact_details",
      { customer_id: contactCustomerId, email: contactEmail || undefined, country: contactCountry || undefined },
      `Update contact details for ${customerName(contactCustomerId)}`
    );
    setContactEmail("");
    setContactCountry("");
  };

  const runProtectedAction = () => {
    if (protectedAction === "pause_subscription") {
      if (!protectedSubscriptionId) return;
      runTool("pause_subscription", { subscription_id: protectedSubscriptionId }, `Pause subscription ${protectedSubscriptionId}`);
    } else if (protectedAction === "reactivate_subscription") {
      if (!protectedSubscriptionId) return;
      runTool("reactivate_subscription", { subscription_id: protectedSubscriptionId }, `Reactivate subscription ${protectedSubscriptionId}`);
    } else if (protectedAction === "change_subscription_plan") {
      if (!protectedSubscriptionId || !protectedNewPlanId) return;
      runTool(
        "change_subscription_plan",
        { subscription_id: protectedSubscriptionId, new_price_plan_id: protectedNewPlanId },
        `Change subscription ${protectedSubscriptionId} to a new plan`
      );
    }
  };

  return (
    <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
      <Box sx={{ flex: 2 }}>
        <Typography variant="h5" gutterBottom>
          AI Assistant
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Your billing assistant. It can answer questions grounded in real data, handle a few routine
          requests directly, and propose protected changes for a human to approve — it can never act
          outside these rules.
        </Typography>

        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
            What it can do
          </Typography>
          <Stack spacing={1}>
            <Typography variant="body2">
              <strong>Answer questions</strong> — customers, subscriptions, invoices, usage, and why an
              invoice changed. Try typing a question below, or use "Look something up" to the right.
            </Typography>
            <Typography variant="body2">
              <strong>Analyze your data in plain language</strong> — e.g. "top 5 customers by revenue",
              "which plan has the most unpaid invoices?", "average invoice by country", "how much AI
              usage did each plan have last month?". It works on whichever workspace you're in (Demo or
              My Workspace) and only reads data — it never changes anything when analyzing.
            </Typography>
            <Typography variant="body2">
              <strong>Handle routine requests</strong> — open a support case, update a customer's contact
              details. Runs immediately (Quick Actions, to the right).
            </Typography>
            <Typography variant="body2">
              <strong>Propose protected changes</strong> — pause/reactivate a
              subscription, change a plan. These are never applied immediately: they wait in "Pending
              Approvals" until a human approves them.
            </Typography>
          </Stack>
        </Paper>

        {(context.customer_id || context.subscription_id || context.invoice_id) && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Context: {context.customer_id && `customer ${context.customer_id} `}
            {context.subscription_id && `subscription ${context.subscription_id} `}
            {context.invoice_id && `invoice ${context.invoice_id}`}
          </Typography>
        )}
        <Paper sx={{ p: 2, mb: 2, minHeight: 300, maxHeight: 500, overflowY: "auto" }}>
          {messages.length === 0 && (
            <Typography color="text.secondary">
              Ask in your own words, e.g. "Which customers bring in the most revenue?", "Generate an invoice for
              Wayne", or "Why did this invoice increase?" (open it from an invoice page for context) — or
              use a Quick Action to the right.
            </Typography>
          )}
          {messages.map((m, idx) => (
            <Box key={idx} sx={{ mb: 2 }}>
              <Typography variant="subtitle2" color={m.role === "user" ? "primary" : "secondary"}>
                {m.role === "user" ? "You" : "AI"}
              </Typography>
              <Typography sx={{ wordBreak: "break-word" }}>{m.text}</Typography>
              {m.verdict && (
                <Chip size="small" color={m.verdict.severity} variant="outlined" label={m.verdict.label} sx={{ mt: 1, mr: 1 }} />
              )}
              {m.toolCalls && m.toolCalls.length > 0 && (
                <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                  {m.toolCalls.map((tc, i) => (
                    <Chip key={i} size="small" label={`${tc.tool}: ${tc.status}`} />
                  ))}
                </Stack>
              )}
            </Box>
          ))}
          {sending && (
            <Typography color="text.secondary" sx={{ fontStyle: "italic" }}>
              AI is working on it — multi-step analysis can take up to a minute or two…
            </Typography>
          )}
        </Paper>
        <Stack direction="row" spacing={1}>
          <TextField
            fullWidth
            placeholder="Ask a question…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <Button variant="contained" onClick={send} disabled={sending}>
            Send
          </Button>
        </Stack>
      </Box>

      <Box sx={{ flex: 1 }}>
        <Typography variant="h6" gutterBottom>
          Quick Actions
        </Typography>

        <Accordion defaultExpanded>
          <AccordionSummary>
            <Typography sx={{ fontWeight: 600 }}>Look something up</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={1.5}>
              <TextField select size="small" label="Type" value={lookupType} onChange={(e) => setLookupType(e.target.value as typeof lookupType)}>
                <MenuItem value="customer">Customer</MenuItem>
                <MenuItem value="subscription">Subscription</MenuItem>
                <MenuItem value="invoice">Invoice</MenuItem>
              </TextField>
              <TextField select size="small" label="Which one" value={lookupId} onChange={(e) => setLookupId(e.target.value)}>
                {lookupType === "customer" && customers.map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
                {lookupType === "subscription" && subscriptions.map((s) => <MenuItem key={s.id} value={s.id}>{s.id}</MenuItem>)}
                {lookupType === "invoice" && invoices.map((i) => <MenuItem key={i.id} value={i.id}>{i.id}</MenuItem>)}
              </TextField>
              <Button variant="outlined" size="small" onClick={runLookup} disabled={!lookupId}>
                Ask AI
              </Button>
            </Stack>
          </AccordionDetails>
        </Accordion>

        <Accordion>
          <AccordionSummary>
            <Typography sx={{ fontWeight: 600 }}>Open a support case</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={1.5}>
              <TextField select size="small" label="Customer" value={caseCustomerId} onChange={(e) => setCaseCustomerId(e.target.value)}>
                {customers.map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
              </TextField>
              <TextField size="small" label="Subject" value={caseSubject} onChange={(e) => setCaseSubject(e.target.value)} />
              <Button variant="outlined" size="small" onClick={runCreateCase} disabled={!caseCustomerId || !caseSubject}>
                Create Case
              </Button>
            </Stack>
          </AccordionDetails>
        </Accordion>

        <Accordion>
          <AccordionSummary>
            <Typography sx={{ fontWeight: 600 }}>Update contact details</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={1.5}>
              <TextField select size="small" label="Customer" value={contactCustomerId} onChange={(e) => setContactCustomerId(e.target.value)}>
                {customers.map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
              </TextField>
              <TextField size="small" label="New email (optional)" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} />
              <TextField size="small" label="New country (optional)" value={contactCountry} onChange={(e) => setContactCountry(e.target.value)} />
              <Button variant="outlined" size="small" onClick={runUpdateContact} disabled={!contactCustomerId}>
                Update
              </Button>
            </Stack>
          </AccordionDetails>
        </Accordion>

        <Accordion>
          <AccordionSummary>
            <Typography sx={{ fontWeight: 600 }}>Request a protected change</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={1.5}>
              <TextField select size="small" label="Action" value={protectedAction} onChange={(e) => setProtectedAction(e.target.value)}>
                {PROTECTED_ACTIONS.map((a) => (
                  <MenuItem key={a.value} value={a.value}>
                    {a.label}
                  </MenuItem>
                ))}
              </TextField>

              {(protectedAction === "pause_subscription" || protectedAction === "reactivate_subscription" || protectedAction === "change_subscription_plan") && (
                <TextField select size="small" label="Subscription" value={protectedSubscriptionId} onChange={(e) => setProtectedSubscriptionId(e.target.value)}>
                  {subscriptions.map((s) => <MenuItem key={s.id} value={s.id}>{s.id}</MenuItem>)}
                </TextField>
              )}

              {protectedAction === "change_subscription_plan" && (
                <TextField select size="small" label="New plan" value={protectedNewPlanId} onChange={(e) => setProtectedNewPlanId(e.target.value)}>
                  {plans.map((p) => <MenuItem key={p.id} value={p.id} sx={{ textTransform: "capitalize" }}>{p.name}</MenuItem>)}
                </TextField>
              )}

              <Button variant="outlined" size="small" onClick={runProtectedAction}>
                Submit for Approval
              </Button>
            </Stack>
          </AccordionDetails>
        </Accordion>

        <Divider sx={{ my: 2 }} />

        <Typography variant="h6" gutterBottom>
          Pending Approvals
        </Typography>
        {approvals.length === 0 && <Typography color="text.secondary">Nothing waiting on approval.</Typography>}
        {approvals.map((a) => (
          <Alert
            key={a.id}
            severity="warning"
            sx={{ mb: 1 }}
            action={
              <Stack direction="row" spacing={1}>
                <Button size="small" onClick={() => resolve(a.id, "approve")}>
                  Approve
                </Button>
                <Button size="small" color="inherit" onClick={() => resolve(a.id, "reject")}>
                  Reject
                </Button>
              </Stack>
            }
          >
            {a.tool} — requested by {a.requested_by}
          </Alert>
        ))}
      </Box>
      <Snackbar
        open={notice !== null}
        autoHideDuration={6000}
        onClose={() => setNotice(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert severity={notice?.severity ?? "info"} variant="filled" onClose={() => setNotice(null)}>
          {notice?.label}
        </Alert>
      </Snackbar>
    </Stack>
  );
}
