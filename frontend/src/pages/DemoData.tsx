import { Button, FormControlLabel, Paper, Radio, RadioGroup, Stack, Switch, Typography } from "@mui/material";
import { useState } from "react";

import { api, getWorkspace } from "../api/client";
import { promptForRefresh } from "../api/dataSync";

const SIZES = [
  { value: "small", label: "Small", detail: "100 customers, ~10,000 events" },
  { value: "medium", label: "Medium", detail: "1,000 customers, ~100,000 events" },
  { value: "large", label: "Large", detail: "10,000 customers, ~1,000,000 events" },
];

export default function DemoData() {
  const [size, setSize] = useState("medium");
  const [includeUci, setIncludeUci] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const workspace = getWorkspace();
  const isDemo = workspace?.workspaceType === "demo";

  const generate = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.post<{ customers: number; usage_events_target: number }>("/demo/generate", {
        size,
        include_uci: includeUci,
      });
      setMessage(`Generated ${result.customers} customers and ~${result.usage_events_target} usage events.`);
      promptForRefresh();
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await api.post("/demo/reset");
      setMessage("Demo environment reset.");
      promptForRefresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Paper sx={{ p: 3, maxWidth: 480 }}>
      <Typography variant="h5" gutterBottom>
        Demo Data
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Generate a realistic example dataset (customers, subscriptions, usage, invoices, payments) to
        explore the platform, or reset it back to empty. Only affects the Demo Workspace.
      </Typography>
      {!isDemo && (
        <Typography color="warning.main" sx={{ mb: 2 }}>
          You're in My Workspace. Switch to Demo Workspace (top right) to generate or reset demo data — real
          workspace data is never touched by this page.
        </Typography>
      )}
      <Typography variant="subtitle1" sx={{ mt: 2 }}>
        Dataset Size
      </Typography>
      <RadioGroup value={size} onChange={(e) => setSize(e.target.value)}>
        {SIZES.map((s) => (
          <FormControlLabel
            key={s.value}
            value={s.value}
            control={<Radio />}
            label={`${s.label} — ${s.detail}`}
          />
        ))}
      </RadioGroup>
      <FormControlLabel
        control={<Switch checked={includeUci} onChange={(e) => setIncludeUci(e.target.checked)} />}
        label="Include UCI transaction data (requires a local dataset file)"
      />
      <Stack direction="row" spacing={2} sx={{ mt: 3 }}>
        <Button variant="contained" onClick={generate} disabled={busy || !isDemo}>
          Generate Demo Environment
        </Button>
        <Button variant="outlined" color="error" onClick={reset} disabled={busy || !isDemo}>
          Reset Demo Environment
        </Button>
      </Stack>
      {message && (
        <Typography sx={{ mt: 2 }} color="text.secondary">
          {message}
        </Typography>
      )}
    </Paper>
  );
}
