import { Chip, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { onDataChanged } from "../api/dataSync";
import { type Customer, type Payment, formatCents } from "../api/types";

export default function Payments() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);

  useEffect(() => {
    const load = () => {
      api.get<Payment[]>("/payments").then(setPayments);
      api.get<Customer[]>("/customers").then(setCustomers);
    };
    load();
    return onDataChanged(load);
  }, []);

  const customerName = (id: string) => customers.find((c) => c.id === id)?.name ?? id;

  return (
    <>
      <Typography variant="h5" gutterBottom>
        Payments
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        A log of every payment attempt and its outcome. Payments are recorded from an invoice's page —
        this view is for reviewing what's succeeded or failed.
      </Typography>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Customer</TableCell>
              <TableCell>Invoice</TableCell>
              <TableCell align="right">Amount</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {payments.map((p) => (
              <TableRow key={p.id}>
                <TableCell>{customerName(p.customer_id)}</TableCell>
                <TableCell>{p.invoice_id}</TableCell>
                <TableCell align="right">{formatCents(p.amount_cents)}</TableCell>
                <TableCell>
                  <Chip size="small" label={p.status} color={p.status === "succeeded" ? "success" : "error"} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}
