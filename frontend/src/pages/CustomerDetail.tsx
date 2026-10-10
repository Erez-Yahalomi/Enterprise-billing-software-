import { Chip, List, ListItemButton, ListItemText, Paper, Stack, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { onDataChanged } from "../api/dataSync";
import { type Customer, type Invoice, type Subscription, formatCents } from "../api/types";

export default function CustomerDetail() {
  const { customerId } = useParams();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);

  useEffect(() => {
    if (!customerId) return;
    const load = () => {
      api.get<Customer>(`/customers/${customerId}`).then(setCustomer);
      api.get<Subscription[]>("/subscriptions").then((all) => setSubscriptions(all.filter((s) => s.customer_id === customerId)));
      api.get<Invoice[]>("/invoices").then((all) => setInvoices(all.filter((i) => i.customer_id === customerId)));
    };
    load();
    return onDataChanged(load);
  }, [customerId]);

  if (!customer) return <Typography>Loading…</Typography>;

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h5">{customer.name}</Typography>
        <Chip label={customer.status} color={customer.status === "active" ? "success" : "default"} />
      </Stack>
      <Typography color="text.secondary">
        Customer ID: {customer.id} · {customer.email} · {customer.country}
      </Typography>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Subscriptions
        </Typography>
        <List>
          {subscriptions.map((s) => (
            <ListItemButton key={s.id} component={Link} to={`/subscriptions/${s.id}`}>
              <ListItemText primary={`${s.id} — ${s.status}`} secondary={`${s.quantity_users} users`} />
            </ListItemButton>
          ))}
          {subscriptions.length === 0 && <Typography color="text.secondary">No subscriptions yet.</Typography>}
        </List>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Invoices
        </Typography>
        <List>
          {invoices.map((inv) => (
            <ListItemButton key={inv.id} component={Link} to={`/invoices/${inv.id}`}>
              <ListItemText
                primary={`${inv.id} — ${formatCents(inv.subtotal_cents)}`}
                secondary={`${inv.period_start} to ${inv.period_end} · ${inv.status}`}
              />
            </ListItemButton>
          ))}
          {invoices.length === 0 && <Typography color="text.secondary">No invoices yet.</Typography>}
        </List>
      </Paper>
    </Stack>
  );
}
