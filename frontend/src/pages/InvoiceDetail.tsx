import { Button, Chip, Paper, Stack, Table, TableBody, TableCell, TableRow, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { onDataChanged, promptForRefresh } from "../api/dataSync";
import { type Invoice, formatCents } from "../api/types";

export default function InvoiceDetail() {
  const { invoiceId } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [paying, setPaying] = useState(false);

  const load = () => {
    if (invoiceId) api.get<Invoice>(`/invoices/${invoiceId}`).then(setInvoice);
  };

  useEffect(() => {
    load();
    return onDataChanged(load);
  }, [invoiceId]);

  const payInvoice = async () => {
    if (!invoice) return;
    setPaying(true);
    try {
      await api.post("/payments", {
        payment_intent_id: `ui-${invoice.id}-${Date.now()}`,
        invoice_id: invoice.id,
        amount_cents: invoice.subtotal_cents,
      });
      load();
      promptForRefresh();
    } finally {
      setPaying(false);
    }
  };

  if (!invoice) return <Typography>Loading…</Typography>;

  return (
    <Paper sx={{ p: 3, maxWidth: 640 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5">Invoice {invoice.id}</Typography>
        <Chip label={invoice.status} color={invoice.status === "paid" ? "success" : "warning"} />
      </Stack>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        {invoice.period_start} — {invoice.period_end}
      </Typography>

      <Table sx={{ mb: 2 }}>
        <TableBody>
          {invoice.line_items.map((li) => (
            <TableRow key={li.id}>
              <TableCell>{li.description}</TableCell>
              <TableCell align="right">{formatCents(li.amount_cents)}</TableCell>
            </TableRow>
          ))}
          <TableRow>
            <TableCell sx={{ fontWeight: "bold" }}>Subtotal</TableCell>
            <TableCell align="right" sx={{ fontWeight: "bold" }}>
              {formatCents(invoice.subtotal_cents)}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <Stack direction="row" spacing={2}>
        <Button variant="outlined" onClick={() => window.print()}>
          Download Invoice
        </Button>
        {invoice.status !== "paid" && (
          <Button variant="contained" onClick={payInvoice} disabled={paying}>
            {paying ? "Processing…" : "Pay Invoice"}
          </Button>
        )}
        <Button variant="outlined" onClick={() => navigate(`/ai?invoice_id=${invoice.id}`)}>
          Ask AI About Invoice
        </Button>
      </Stack>
    </Paper>
  );
}
