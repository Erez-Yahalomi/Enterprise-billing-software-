import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { onDataChanged, promptForRefresh } from "../api/dataSync";
import { type Subscription, type UsageByDayItem, currentMonthBounds, toLocalIsoDate } from "../api/types";

const EVENT_TYPES = [
  "api_request",
  "storage_gb",
  "ai_tokens",
  "document_processed",
  "report_generated",
  "data_export",
  "user_login",
];

function todayIso(): string {
  return toLocalIsoDate(new Date());
}

export default function Usage() {
  const [params, setParams] = useSearchParams();
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [subscriptionId, setSubscriptionId] = useState(params.get("subscription_id") ?? "");
  const [items, setItems] = useState<UsageByDayItem[]>([]);
  const { start, end } = currentMonthBounds();

  const [open, setOpen] = useState(false);
  const [formSubscriptionId, setFormSubscriptionId] = useState("");
  const [eventType, setEventType] = useState(EVENT_TYPES[0]);
  const [quantity, setQuantity] = useState("100");
  const [occurredOn, setOccurredOn] = useState(todayIso());

  const loadSubscriptions = () =>
    api.get<Subscription[]>("/subscriptions").then((subs) => {
      setSubscriptions(subs);
      if (!subscriptionId && subs.length > 0) setSubscriptionId(subs[0].id);
    });

  useEffect(() => {
    loadSubscriptions();
    return onDataChanged(loadSubscriptions);
  }, []);

  const loadUsage = () => {
    if (!subscriptionId) return;
    setParams({ subscription_id: subscriptionId });
    api
      .get<UsageByDayItem[]>(`/analytics/usage-by-day?subscription_id=${subscriptionId}&period_start=${start}&period_end=${end}`)
      .then(setItems);
  };

  useEffect(() => {
    loadUsage();
    return onDataChanged(loadUsage);
  }, [subscriptionId]);

  const openDialog = () => {
    setFormSubscriptionId(subscriptionId || subscriptions[0]?.id || "");
    setEventType(EVENT_TYPES[0]);
    setQuantity("100");
    setOccurredOn(todayIso());
    setOpen(true);
  };

  const recordUsage = async () => {
    const subscription = subscriptions.find((s) => s.id === formSubscriptionId);
    if (!subscription) return;
    await api.post("/usage", {
      event_id: `ui-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      customer_id: subscription.customer_id,
      subscription_id: subscription.id,
      event_type: eventType,
      quantity: parseInt(quantity || "0", 10),
      occurred_at: new Date(`${occurredOn}T12:00:00Z`).toISOString(),
    });
    setOpen(false);
    // The Kafka pipeline aggregates asynchronously in the real deployment, so the chart
    // may take a moment to reflect a just-recorded event.
    setTimeout(loadUsage, 1500);
    promptForRefresh();
  };

  return (
    <>
      <Typography variant="h5" gutterBottom>
        Usage (current month)
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Day-by-day usage for a subscription — this is what usage-based charges on its next invoice are
        calculated from. Pick a subscription below to see its breakdown by type, or record usage manually.
      </Typography>

      <Stack direction="row" spacing={2} sx={{ mb: 2 }} alignItems="center">
        <TextField
          select
          label="Subscription"
          value={subscriptionId}
          onChange={(e) => setSubscriptionId(e.target.value)}
          sx={{ minWidth: 320 }}
        >
          {subscriptions.map((s) => (
            <MenuItem key={s.id} value={s.id}>
              {s.id}
            </MenuItem>
          ))}
        </TextField>
        <Button variant="contained" onClick={openDialog} disabled={subscriptions.length === 0}>
          Record Usage
        </Button>
      </Stack>
      {subscriptions.length === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          You need a subscription first — see the Subscriptions page.
        </Typography>
      )}

      <Paper>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Day</TableCell>
              <TableCell>Type</TableCell>
              <TableCell align="right">Quantity</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item, idx) => (
              <TableRow key={idx}>
                <TableCell>{item.day}</TableCell>
                <TableCell>{item.event_type}</TableCell>
                <TableCell align="right">{item.total_quantity.toLocaleString()}</TableCell>
              </TableRow>
            ))}
            {items.length === 0 && (
              <TableRow>
                <TableCell colSpan={3}>
                  <Typography color="text.secondary">No usage recorded yet this month.</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>

      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>Record Usage</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 320, pt: "12px !important" }}>
          <TextField
            select
            label="Subscription"
            value={formSubscriptionId}
            onChange={(e) => setFormSubscriptionId(e.target.value)}
          >
            {subscriptions.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.id}
              </MenuItem>
            ))}
          </TextField>
          <TextField select label="Event type" value={eventType} onChange={(e) => setEventType(e.target.value)}>
            {EVENT_TYPES.map((t) => (
              <MenuItem key={t} value={t}>
                {t}
              </MenuItem>
            ))}
          </TextField>
          <TextField label="Quantity" type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          <TextField
            label="Date"
            type="date"
            value={occurredOn}
            onChange={(e) => setOccurredOn(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={recordUsage} disabled={!formSubscriptionId}>
            Record
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
