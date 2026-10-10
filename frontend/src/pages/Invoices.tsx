import {
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { onDataChanged, promptForRefresh } from "../api/dataSync";
import { type Customer, type Invoice, type Subscription, currentMonthBounds, formatCents } from "../api/types";

const STATUS_COLOR: Record<string, "success" | "warning" | "default" | "error"> = {
  paid: "success",
  finalized: "warning",
  draft: "default",
  void: "error",
};

export default function Invoices() {
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);

  const [open, setOpen] = useState(false);
  const [subscriptionId, setSubscriptionId] = useState("");
  const { start, end } = currentMonthBounds();
  const [periodStart, setPeriodStart] = useState(start);
  const [periodEnd, setPeriodEnd] = useState(end);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    api.get<Invoice[]>("/invoices").then(setInvoices);
    api.get<Customer[]>("/customers").then(setCustomers);
    api.get<Subscription[]>("/subscriptions").then(setSubscriptions);
  };

  useEffect(() => {
    load();
    return onDataChanged(load);
  }, []);

  const customerName = (id: string) => customers.find((c) => c.id === id)?.name ?? id;

  const openDialog = () => {
    setSubscriptionId(subscriptions[0]?.id ?? "");
    setPeriodStart(start);
    setPeriodEnd(end);
    setError(null);
    setOpen(true);
  };

  const generateInvoice = async () => {
    setError(null);
    try {
      const invoice = await api.post<Invoice>("/invoices/generate", {
        subscription_id: subscriptionId,
        period_start: periodStart,
        period_end: periodEnd,
      });
      setOpen(false);
      promptForRefresh();
      navigate(`/invoices/${invoice.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate invoice.");
    }
  };

  return (
    <>
      <Typography variant="h5" gutterBottom>
        Invoices
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Every bill generated for a customer. Click one to see its line items, pay it, download it, or
        ask the AI Assistant about it.
      </Typography>

      <Button variant="contained" sx={{ mb: 2 }} onClick={openDialog} disabled={subscriptions.length === 0}>
        Generate Invoice
      </Button>
      {subscriptions.length === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          You need a subscription first — see the Subscriptions page.
        </Typography>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Invoice</TableCell>
              <TableCell>Customer</TableCell>
              <TableCell>Period</TableCell>
              <TableCell align="right">Amount</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {invoices.map((inv) => (
              <TableRow key={inv.id} hover component={Link} to={`/invoices/${inv.id}`} sx={{ textDecoration: "none" }}>
                <TableCell>{inv.id}</TableCell>
                <TableCell>{customerName(inv.customer_id)}</TableCell>
                <TableCell>
                  {inv.period_start} — {inv.period_end}
                </TableCell>
                <TableCell align="right">{formatCents(inv.subtotal_cents)}</TableCell>
                <TableCell>
                  <Chip size="small" label={inv.status} color={STATUS_COLOR[inv.status] ?? "default"} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>Generate Invoice</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 320, pt: "12px !important" }}>
          <TextField
            select
            label="Subscription"
            value={subscriptionId}
            onChange={(e) => setSubscriptionId(e.target.value)}
          >
            {subscriptions.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.id} — {customerName(s.customer_id)}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Period start"
            type="date"
            value={periodStart}
            onChange={(e) => setPeriodStart(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label="Period end"
            type="date"
            value={periodEnd}
            onChange={(e) => setPeriodEnd(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
          {error && (
            <Typography color="error" variant="body2">
              {error}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={generateInvoice} disabled={!subscriptionId}>
            Generate
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
