import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
import type { Customer } from "../api/types";

export default function Customers() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [country, setCountry] = useState("");

  const load = () => api.get<Customer[]>("/customers").then(setCustomers);

  useEffect(() => {
    load();
    return onDataChanged(load);
  }, []);

  const createCustomer = async () => {
    await api.post("/customers", { name, email, country: country || null });
    setOpen(false);
    setName("");
    setEmail("");
    setCountry("");
    load();
    promptForRefresh();
  };

  return (
    <>
      <Typography variant="h5" gutterBottom>
        Customers
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Every company or person you bill. Click "New Customer" to register one, or click any row to see
        their subscriptions and invoices.
      </Typography>
      <Button variant="contained" sx={{ mb: 2 }} onClick={() => setOpen(true)}>
        New Customer
      </Button>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Customer</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Country</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {customers.map((c) => (
              <TableRow key={c.id} hover component={Link} to={`/customers/${c.id}`} sx={{ textDecoration: "none" }}>
                <TableCell>{c.name}</TableCell>
                <TableCell>{c.email}</TableCell>
                <TableCell>{c.country}</TableCell>
                <TableCell>{c.status}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>New Customer</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 320, pt: "12px !important" }}>
          <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          <TextField label="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <TextField label="Country" value={country} onChange={(e) => setCountry(e.target.value)} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={createCustomer} disabled={!name || !email}>
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
