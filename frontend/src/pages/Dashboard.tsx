import { Card, CardContent, Grid, Typography } from "@mui/material";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { onDataChanged } from "../api/dataSync";
import { type Customer, type Invoice, type Payment, type Subscription, formatCents } from "../api/types";

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Grid item xs={12} sm={6} md={3}>
      <Card>
        <CardContent>
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
          <Typography variant="h5">{value}</Typography>
        </CardContent>
      </Card>
    </Grid>
  );
}

export default function Dashboard() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    Promise.all([
      api.get<Customer[]>("/customers"),
      api.get<Subscription[]>("/subscriptions"),
      api.get<Invoice[]>("/invoices"),
      api.get<Payment[]>("/payments"),
    ])
      .then(([c, s, i, p]) => {
        setCustomers(c);
        setSubscriptions(s);
        setInvoices(i);
        setPayments(p);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    return onDataChanged(load);
  }, []);

  if (loading) return <Typography>Loading…</Typography>;

  const monthlyRevenue = payments.filter((p) => p.status === "succeeded").reduce((sum, p) => sum + p.amount_cents, 0);
  const activeSubscriptions = subscriptions.filter((s) => s.status === "active").length;
  const openInvoices = invoices.filter((i) => i.status === "finalized").length;
  const failedPayments = payments.filter((p) => p.status === "failed").length;

  return (
    <>
      <Typography variant="h5" gutterBottom>
        Dashboard
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        A quick snapshot of the business across the current workspace. Watch "Failed Payments" and
        "Open Invoices" here for early warning signs — click through to Payments or Invoices for detail.
      </Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <StatCard label="Collected Revenue" value={formatCents(monthlyRevenue)} />
        <StatCard label="Active Subscriptions" value={String(activeSubscriptions)} />
        <StatCard label="Customers" value={String(customers.length)} />
        <StatCard label="Open Invoices" value={String(openInvoices)} />
        <StatCard label="Failed Payments" value={String(failedPayments)} />
        <StatCard label="Total Invoices" value={String(invoices.length)} />
      </Grid>
    </>
  );
}
