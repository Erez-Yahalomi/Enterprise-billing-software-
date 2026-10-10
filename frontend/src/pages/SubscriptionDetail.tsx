import { Button, Paper, Stack, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { onDataChanged } from "../api/dataSync";
import { type PricePlan, type Subscription, formatCents } from "../api/types";

export default function SubscriptionDetail() {
  const { subscriptionId } = useParams();
  const navigate = useNavigate();
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [plan, setPlan] = useState<PricePlan | null>(null);

  useEffect(() => {
    if (!subscriptionId) return;
    const load = () => {
      api.get<Subscription>(`/subscriptions/${subscriptionId}`).then((s) => {
        setSubscription(s);
        api.get<PricePlan[]>("/price-plans").then((plans) => setPlan(plans.find((p) => p.id === s.price_plan_id) ?? null));
      });
    };
    load();
    return onDataChanged(load);
  }, [subscriptionId]);

  if (!subscription) return <Typography>Loading…</Typography>;

  return (
    <Paper sx={{ p: 3, maxWidth: 560 }}>
      <Typography variant="h5" gutterBottom sx={{ textTransform: "capitalize" }}>
        {plan?.name ?? "Subscription"}
      </Typography>
      <Stack spacing={1} sx={{ mb: 3 }}>
        <Typography>Subscription ID: {subscription.id}</Typography>
        <Typography>Status: {subscription.status}</Typography>
        <Typography>Started: {new Date(subscription.started_at).toLocaleDateString()}</Typography>
        <Typography>Users: {subscription.quantity_users}</Typography>
        {plan && (
          <>
            <Typography>Monthly base price: {formatCents(plan.monthly_price_cents)}</Typography>
            <Typography>Included API calls: {plan.included_api_calls.toLocaleString()}</Typography>
            <Typography>
              Additional API price: {formatCents(plan.overage_api_price_cents_per_unit)} / call
            </Typography>
          </>
        )}
      </Stack>
      <Stack direction="row" spacing={2}>
        <Button variant="outlined" onClick={() => navigate(`/usage?subscription_id=${subscription.id}`)}>
          View Usage
        </Button>
        <Button
          variant="outlined"
          onClick={() => navigate(`/ai?subscription_id=${subscription.id}`)}
        >
          Ask AI About This Subscription
        </Button>
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 2 }}>
        Protected changes (plan changes, pausing) go through the AI Assistant and require approval.
      </Typography>
    </Paper>
  );
}
