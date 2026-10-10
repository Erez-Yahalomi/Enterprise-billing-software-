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
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { onDataChanged, promptForRefresh } from "../api/dataSync";
import { type PricePlan, type Product, formatCents } from "../api/types";

const emptyPlanForm = {
  product_id: "",
  name: "",
  monthly_price: "",
  included_users: "0",
  additional_user_price: "0",
  included_api_calls: "0",
  overage_api_price: "0",
  ai_token_price_per_1k: "0",
  storage_gb_price: "0",
};

export default function Products() {
  const [products, setProducts] = useState<Product[]>([]);
  const [plans, setPlans] = useState<PricePlan[]>([]);

  const [productDialogOpen, setProductDialogOpen] = useState(false);
  const [productName, setProductName] = useState("");
  const [productCode, setProductCode] = useState("");

  const [planDialogOpen, setPlanDialogOpen] = useState(false);
  const [planForm, setPlanForm] = useState(emptyPlanForm);

  const load = () => {
    api.get<Product[]>("/products").then(setProducts).catch(() => setProducts([]));
    api.get<PricePlan[]>("/price-plans").then(setPlans);
  };

  useEffect(() => {
    load();
    return onDataChanged(load);
  }, []);

  const productName_ = (id: string) => products.find((p) => p.id === id)?.name ?? id;

  const createProduct = async () => {
    await api.post("/products", { name: productName, code: productCode });
    setProductDialogOpen(false);
    setProductName("");
    setProductCode("");
    load();
    promptForRefresh();
  };

  const openPlanDialog = () => {
    setPlanForm({ ...emptyPlanForm, product_id: products[0]?.id ?? "" });
    setPlanDialogOpen(true);
  };

  const dollarsToCents = (v: string) => Math.round(parseFloat(v || "0") * 100);

  const createPlan = async () => {
    await api.post("/price-plans", {
      product_id: planForm.product_id,
      name: planForm.name,
      monthly_price_cents: dollarsToCents(planForm.monthly_price),
      included_users: parseInt(planForm.included_users || "0", 10),
      additional_user_price_cents: dollarsToCents(planForm.additional_user_price),
      included_api_calls: parseInt(planForm.included_api_calls || "0", 10),
      overage_api_price_cents_per_unit: dollarsToCents(planForm.overage_api_price),
      ai_token_price_cents_per_1k: dollarsToCents(planForm.ai_token_price_per_1k),
      storage_gb_price_cents: dollarsToCents(planForm.storage_gb_price),
    });
    setPlanDialogOpen(false);
    load();
    promptForRefresh();
  };

  return (
    <>
      <Typography variant="h5" gutterBottom>
        Products &amp; Price Plans
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        The products you sell and the pricing plans customers subscribe to. Create at least one product
        and one price plan here before creating subscriptions.
      </Typography>

      <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
        <Button variant="contained" onClick={() => setProductDialogOpen(true)}>
          New Product
        </Button>
        <Button variant="contained" onClick={openPlanDialog} disabled={products.length === 0}>
          New Price Plan
        </Button>
      </Stack>

      <Typography variant="h6" gutterBottom>
        Products
      </Typography>
      <TableContainer component={Paper} sx={{ mb: 3 }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Code</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {products.map((p) => (
              <TableRow key={p.id}>
                <TableCell>{p.name}</TableCell>
                <TableCell>{p.code}</TableCell>
              </TableRow>
            ))}
            {products.length === 0 && (
              <TableRow>
                <TableCell colSpan={2}>
                  <Typography color="text.secondary">No products yet — create one above.</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Typography variant="h6" gutterBottom>
        Price Plans
      </Typography>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Plan</TableCell>
              <TableCell>Product</TableCell>
              <TableCell align="right">Monthly Price</TableCell>
              <TableCell align="right">Included Users</TableCell>
              <TableCell align="right">Included API Calls</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {plans.map((plan) => (
              <TableRow key={plan.id}>
                <TableCell sx={{ textTransform: "capitalize" }}>{plan.name}</TableCell>
                <TableCell>{productName_(plan.product_id)}</TableCell>
                <TableCell align="right">{formatCents(plan.monthly_price_cents)}</TableCell>
                <TableCell align="right">{plan.included_users}</TableCell>
                <TableCell align="right">{plan.included_api_calls.toLocaleString()}</TableCell>
              </TableRow>
            ))}
            {plans.length === 0 && (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography color="text.secondary">No price plans yet — create one above.</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={productDialogOpen} onClose={() => setProductDialogOpen(false)}>
        <DialogTitle>New Product</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 320, pt: "12px !important" }}>
          <TextField label="Name" value={productName} onChange={(e) => setProductName(e.target.value)} autoFocus />
          <TextField label="Code" value={productCode} onChange={(e) => setProductCode(e.target.value)} helperText="A short internal identifier, e.g. 'core'" />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setProductDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={createProduct} disabled={!productName || !productCode}>
            Create
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={planDialogOpen} onClose={() => setPlanDialogOpen(false)}>
        <DialogTitle>New Price Plan</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 360, pt: "12px !important" }}>
          <TextField
            select
            label="Product"
            value={planForm.product_id}
            onChange={(e) => setPlanForm({ ...planForm, product_id: e.target.value })}
          >
            {products.map((p) => (
              <MenuItem key={p.id} value={p.id}>
                {p.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Plan name"
            value={planForm.name}
            onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })}
            helperText="e.g. starter, professional, enterprise"
          />
          <TextField
            label="Monthly price ($)"
            type="number"
            value={planForm.monthly_price}
            onChange={(e) => setPlanForm({ ...planForm, monthly_price: e.target.value })}
          />
          <Stack direction="row" spacing={2}>
            <TextField
              label="Included users"
              type="number"
              value={planForm.included_users}
              onChange={(e) => setPlanForm({ ...planForm, included_users: e.target.value })}
              fullWidth
            />
            <TextField
              label="Price per extra user ($)"
              type="number"
              value={planForm.additional_user_price}
              onChange={(e) => setPlanForm({ ...planForm, additional_user_price: e.target.value })}
              fullWidth
            />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField
              label="Included API calls"
              type="number"
              value={planForm.included_api_calls}
              onChange={(e) => setPlanForm({ ...planForm, included_api_calls: e.target.value })}
              fullWidth
            />
            <TextField
              label="Price per extra call ($)"
              type="number"
              value={planForm.overage_api_price}
              onChange={(e) => setPlanForm({ ...planForm, overage_api_price: e.target.value })}
              fullWidth
            />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField
              label="AI price per 1k tokens ($)"
              type="number"
              value={planForm.ai_token_price_per_1k}
              onChange={(e) => setPlanForm({ ...planForm, ai_token_price_per_1k: e.target.value })}
              fullWidth
            />
            <TextField
              label="Storage price per GB ($)"
              type="number"
              value={planForm.storage_gb_price}
              onChange={(e) => setPlanForm({ ...planForm, storage_gb_price: e.target.value })}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPlanDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={createPlan} disabled={!planForm.product_id || !planForm.name || !planForm.monthly_price}>
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
