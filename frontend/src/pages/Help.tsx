import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  List,
  ListItem,
  ListItemText,
  Paper,
  Typography,
} from "@mui/material";

interface Section {
  title: string;
  purpose: string;
  howTo: string[];
}

const SECTIONS: Section[] = [
  {
    title: "Dashboard",
    purpose: "A quick, at-a-glance snapshot of the business: collected revenue, active subscriptions, customer count, open invoices, and failed payments.",
    howTo: [
      "Open it any time from the sidebar — it's the home page.",
      "Numbers update automatically based on whichever workspace you're in (Demo or My Workspace).",
      "Use it to spot problems quickly: a high 'Failed Payments' or 'Open Invoices' count is a signal to check the Payments or Invoices pages.",
    ],
  },
  {
    title: "Customers",
    purpose: "Manage the companies or people you bill. Every subscription and invoice belongs to a customer.",
    howTo: [
      "Click 'New Customer' to register someone — you only need a name and email (country is optional).",
      "Click any row to open that customer's detail page, which lists their subscriptions and invoices.",
      "In Demo Workspace, this list is pre-populated (including named example customers like ACME and Globex) so you can explore without creating anything yourself.",
    ],
  },
  {
    title: "Products & Plans",
    purpose: "Define what you sell (products) and the pricing plans customers subscribe to — the fixed monthly fee plus any usage-based rates (extra users, API overage, AI tokens, storage).",
    howTo: [
      "Create a product first (e.g. 'Billing Platform'), then one or more price plans under it (e.g. 'starter', 'professional').",
      "You need at least one price plan before you can create a subscription, so this is usually the first thing to set up in a new workspace.",
      "Prices are entered in dollars and converted to cents automatically. Saving a plan with the same name again creates a new version rather than overwriting it — past invoices keep the pricing they were billed under.",
    ],
  },
  {
    title: "Subscriptions",
    purpose: "Shows which pricing plan each customer is on, how many users they have, and whether the subscription is active, paused, or canceled.",
    howTo: [
      "Click 'New Subscription' to put a customer on a price plan (requires at least one customer and one price plan to exist first).",
      "Click a row to open its detail page, which shows the plan's pricing and allowances.",
      "From there, 'View Usage' jumps to that subscription's usage chart, and 'Ask AI About This Subscription' opens the AI Assistant with that subscription pre-loaded as context.",
      "Changing a subscription's plan or pausing it is a protected action — it's done through the AI Assistant and requires a human to approve it, not a direct edit here.",
    ],
  },
  {
    title: "Usage",
    purpose: "Shows day-by-day usage (API calls, AI tokens, storage, etc.) for a subscription over the current month — this is what usage-based billing is calculated from.",
    howTo: [
      "Pick a subscription from the dropdown to see its usage broken down by day and type.",
      "Click 'Record Usage' to log usage manually — useful for trying out usage-based billing without waiting for real traffic.",
      "This data is what the billing engine reads when generating an invoice, so it's useful for understanding why a bill came out the way it did.",
    ],
  },
  {
    title: "Invoices",
    purpose: "Every bill generated for a customer: the fixed subscription fee plus any usage-based charges for that period.",
    howTo: [
      "Click 'Generate Invoice', pick a subscription and a period, and the billing engine calculates the charges from that period's recorded usage.",
      "Click a row to open the invoice, which itemizes exactly where each charge came from (base fee, extra users, API overage, AI usage, storage).",
      "'Pay Invoice' records a payment against it (uses a safe mock payment provider — no real money moves).",
      "'Download Invoice' opens a printable view.",
      "'Ask AI About Invoice' opens the AI Assistant with that invoice as context — great for questions like \"why is this higher than last month?\"",
    ],
  },
  {
    title: "Payments",
    purpose: "A log of every payment attempt and whether it succeeded or failed.",
    howTo: [
      "Browse to see which customers have paid and which payments failed (useful for spotting at-risk accounts).",
      "Payments are recorded from the Invoice detail page — there's nothing to do on this page itself besides review.",
    ],
  },
  {
    title: "Analytics",
    purpose: "Business-level metrics: recognized revenue, Monthly/Annual Recurring Revenue (MRR/ARR), how customers are distributed across plans, and which invoices are still open.",
    howTo: [
      "Use this for a higher-level view than the Dashboard — it's aimed at understanding trends across the whole customer base rather than day-to-day operations.",
    ],
  },
  {
    title: "AI Assistant",
    purpose: "A chat-based billing assistant that can look up customers, subscriptions, invoices and usage, and — with approval — make certain changes on your behalf.",
    howTo: [
      "Type a question in plain English, e.g. \"Why did this invoice increase?\" It works best when opened from an Invoice, Subscription, or Customer page via an 'Ask AI' button, since that gives it context to work with.",
      "For anything beyond a question, use the 'Quick Actions' panel on the right instead of trying to phrase it as a chat message — it has a guided form for every action the AI can take: looking something up, opening a support case, updating a customer's contact details, or requesting a protected change. This guarantees the action runs correctly rather than depending on how you word it.",
      "Every answer is grounded in real data pulled through specific tools (shown as small chips under each reply) — the AI never invents numbers.",
      "Some actions (pausing a subscription, changing a plan) are protected: the AI submits them for approval instead of doing them immediately. You'll see them under 'Pending Approvals' on this page, where an admin can approve or reject them.",
      "The AI cannot run raw database queries, execute code, or bypass these checks — that's enforced by the platform, not just good behavior on its part.",
    ],
  },
  {
    title: "Demo Data",
    purpose: "Generates or resets the realistic example data used in the Demo Workspace, so you can explore the platform without setting anything up yourself.",
    howTo: [
      "Only works while you're in the Demo Workspace (switch to it using the selector in the top-right if needed).",
      "Pick a size (Small/Medium/Large) and click 'Generate Demo Environment' to (re)create a full dataset — customers, subscriptions, usage, invoices, and payments, including a few named examples with specific stories (a usage spike, a failed payment, a plan upgrade, and so on).",
      "'Reset Demo Environment' wipes the demo data clean. It never touches My Workspace.",
    ],
  },
];

export default function Help() {
  return (
    <Box sx={{ maxWidth: 900 }}>
      <Typography variant="h5" gutterBottom>
        How to Use This Platform
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        The Corporate Billing Platform manages the full lifecycle of billing a customer: registering
        them, putting them on a subscription plan, tracking their usage, generating invoices, and
        collecting payment — with an AI assistant to help answer questions and handle routine requests.
      </Typography>

      <Alert severity="info" sx={{ mb: 2 }}>
        Use the workspace selector in the top-right corner to switch between the <strong>Demo
        Workspace</strong> (safe, preloaded example data — reset it anytime from the Demo Data page)
        and <strong>My Workspace</strong> (your own real data, which starts empty). The two never mix.
      </Alert>

      <Alert severity="info" sx={{ mb: 3 }}>
        Whenever you save something, a page reflects it immediately. Since data you enter in one place
        (a new customer, a price plan, a subscription) is often used by others, you'll also see a
        banner at the bottom of the screen asking "Update every other open page with this change?" —
        choose <strong>Update All</strong> to make sure every page reflects it right away, or "Not
        now" if you're still mid-flow (you'll always see the latest data next time you open a page
        anyway).
      </Alert>

      <Paper variant="outlined">
        {SECTIONS.map((section) => (
          <Accordion key={section.title} disableGutters>
            <AccordionSummary sx={{ fontWeight: "bold" }}>
              <Typography sx={{ fontWeight: 600 }}>{section.title}</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography sx={{ mb: 1.5 }}>{section.purpose}</Typography>
              <List dense disablePadding>
                {section.howTo.map((line, idx) => (
                  <ListItem key={idx} sx={{ display: "list-item", listStyleType: "disc", ml: 3, py: 0.25 }}>
                    <ListItemText primary={line} />
                  </ListItem>
                ))}
              </List>
            </AccordionDetails>
          </Accordion>
        ))}
      </Paper>
    </Box>
  );
}
