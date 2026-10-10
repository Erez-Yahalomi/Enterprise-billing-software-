import {
  Button,
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
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { onDataChanged, promptForRefresh } from "../api/dataSync";
import type { Customer, PricePlan, Subscription } from "../api/types";

export default function Subscriptions() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [plans, setPlans] = useState<PricePlan[]>([]);

  const [open, setOpen] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [planId, setPlanId] = useState("");
  const [quantityUsers, setQuantityUsers] = useState("1");

  const load = () => {
    api.get<Subscription[]>("/subscriptions").then(setSubscriptions);
    api.get<Customer[]>("/customers").then(setCustomers);
    api.get<PricePlan[]>("/price-plans").then(setPlans);
  };

  useEffect(() => {
    load();
    return onDataChanged(load);
  }, []);

  const customerName = (id: string) => customers.find((c) => c.id === id)?.name ?? id;
  const planName = (id: string) => plans.find((p) => p.id === id)?.name ?? id;

  const openDialog = () => {
    setCustomerId(customers[0]?.id ?? "");
    setPlanId(plans[0]?.id ?? "");
    setQuantityUsers("1");
    setOpen(true);
  };

  const createSubscription = async () => {
    await api.post("/subscriptions", {
      customer_id: customerId,
      price_plan_id: planId,
      quantity_users: parseInt(quantityUsers || "1", 10),
    });
    setOpen(false);
    load();
    promptForRefresh();
  };

  return (
    <>
      <Typography variant="h5" gutterBottom>
        Subscriptions
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Which plan each customer is on and its status. Click a row for plan details and usage — plan
        changes and pausing are protected actions, handled via the AI Assistant with approval.
      </Typography>

      <Button
        variant="contained"
        sx={{ mb: 2 }}
        onClick={openDialog}
        disabled={customers.length === 0 || plans.length === 0}
      >
        New Subscription
      </Button>
      {(customers.length === 0 || plans.length === 0) && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          You need at least one customer and one price plan first — see the Customers and Products &amp;
          Price Plans pages.
        </Typography>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Customer</TableCell>
              <TableCell>Plan</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Users</TableCell>
              <TableCell>Started</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {subscriptions.map((s) => (
              <TableRow key={s.id} hover component={Link} to={`/subscriptions/${s.id}`} sx={{ textDecoration: "none" }}>
                <TableCell>{customerName(s.customer_id)}</TableCell>
                <TableCell sx={{ textTransform: "capitalize" }}>{planName(s.price_plan_id)}</TableCell>
                <TableCell sx={{ textTransform: "capitalize" }}>{s.status}</TableCell>
                <TableCell>{s.quantity_users}</TableCell>
                <TableCell>{new Date(s.started_at).toLocaleDateString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>New Subscription</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 320, pt: "12px !important" }}>
          <TextField select label="Customer" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            {customers.map((c) => (
              <MenuItem key={c.id} value={c.id}>
                {c.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField select label="Price plan" value={planId} onChange={(e) => setPlanId(e.target.value)}>
            {plans.map((p) => (
              <MenuItem key={p.id} value={p.id} sx={{ textTransform: "capitalize" }}>
                {p.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Users"
            type="number"
            value={quantityUsers}
            onChange={(e) => setQuantityUsers(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={createSubscription} disabled={!customerId || !planId}>
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
