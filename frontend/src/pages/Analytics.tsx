import { Grid, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { onDataChanged } from "../api/dataSync";
import { type Invoice, type PricePlan, type Subscription, formatCents } from "../api/types";

export default function Analytics() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [plans, setPlans] = useState<PricePlan[]>([]);

  useEffect(() => {
    const load = () => {
      api.get<Invoice[]>("/invoices").then(setInvoices);
      api.get<Subscription[]>("/subscriptions").then(setSubscriptions);
      api.get<PricePlan[]>("/price-plans").then(setPlans);
    };
    load();
    return onDataChanged(load);
  }, []);

  const paidInvoices = invoices.filter((i) => i.status === "paid");
  const revenue = paidInvoices.reduce((sum, i) => sum + i.subtotal_cents, 0);
  const activeSubs = subscriptions.filter((s) => s.status === "active");
  const mrr = activeSubs.reduce((sum, s) => {
    const plan = plans.find((p) => p.id === s.price_plan_id);
    return sum + (plan?.monthly_price_cents ?? 0);
  }, 0);
  const arr = mrr * 12;

  const planDistribution = plans.map((plan) => ({
    plan,
    count: subscriptions.filter((s) => s.price_plan_id === plan.id).length,
  }));

  const overdue = invoices.filter((i) => i.status === "finalized");

  return (
    <>
      <Typography variant="h5" gutterBottom>
        Analytics
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Business-level trends across the whole customer base — revenue, MRR/ARR, how customers are
        spread across plans, and which invoices are still open.
      </Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={4}>
          <Paper sx={{ p: 2 }}>
            <Typography color="text.secondary">Recognized Revenue (paid)</Typography>
            <Typography variant="h5">{formatCents(revenue)}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Paper sx={{ p: 2 }}>
            <Typography color="text.secondary">MRR</Typography>
            <Typography variant="h5">{formatCents(mrr)}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Paper sx={{ p: 2 }}>
            <Typography color="text.secondary">ARR</Typography>
            <Typography variant="h5">{formatCents(arr)}</Typography>
          </Paper>
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Plan Distribution
            </Typography>
            <Table>
              <TableBody>
                {planDistribution.map(({ plan, count }) => (
                  <TableRow key={plan.id}>
                    <TableCell sx={{ textTransform: "capitalize" }}>{plan.name}</TableCell>
                    <TableCell align="right">{count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Overdue / Open Invoices ({overdue.length})
            </Typography>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Invoice</TableCell>
                  <TableCell align="right">Amount</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {overdue.slice(0, 10).map((inv) => (
                  <TableRow key={inv.id}>
                    <TableCell>{inv.id}</TableCell>
                    <TableCell align="right">{formatCents(inv.subtotal_cents)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        </Grid>
      </Grid>
    </>
  );
}
