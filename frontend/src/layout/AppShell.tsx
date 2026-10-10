import {
  AppBar,
  Box,
  Button,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Select,
  Snackbar,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";

import { getWorkspace, startDemoWorkspace, startMyWorkspace, type Workspace } from "../api/client";
import { refreshAllData, registerRefreshPrompt } from "../api/dataSync";

const DRAWER_WIDTH = 220;

const NAV_ITEMS = [
  { label: "Dashboard", path: "/" },
  { label: "Customers", path: "/customers" },
  { label: "Products & Plans", path: "/products" },
  { label: "Subscriptions", path: "/subscriptions" },
  { label: "Usage", path: "/usage" },
  { label: "Invoices", path: "/invoices" },
  { label: "Payments", path: "/payments" },
  { label: "Analytics", path: "/analytics" },
  { label: "AI Assistant", path: "/ai" },
  { label: "Demo Data", path: "/demo-data" },
  { label: "Help", path: "/help" },
];

export default function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [workspace, setWorkspaceState] = useState<Workspace>(() => getWorkspace() ?? startDemoWorkspace());
  const [refreshPromptOpen, setRefreshPromptOpen] = useState(false);

  useEffect(() => registerRefreshPrompt(() => setRefreshPromptOpen(true)), []);

  const handleRefreshAll = () => {
    refreshAllData();
    setRefreshPromptOpen(false);
  };

  const handleWorkspaceChange = (value: string) => {
    const next = value === "demo" ? startDemoWorkspace() : startMyWorkspace();
    setWorkspaceState(next);
    navigate("/");
    window.location.reload();
  };

  return (
    <Box sx={{ display: "flex" }}>
      <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
        <Toolbar sx={{ display: "flex", justifyContent: "space-between" }}>
          <Typography variant="h6" noWrap>
            Corporate Billing Platform
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Select
              size="small"
              value={workspace.workspaceType}
              onChange={(e) => handleWorkspaceChange(e.target.value)}
              sx={{ bgcolor: "background.paper", minWidth: 180 }}
            >
              <MenuItem value="demo">Demo Workspace</MenuItem>
              <MenuItem value="production">My Workspace</MenuItem>
            </Select>
            <Tooltip title="How to use this platform">
              <IconButton
                component={Link}
                to="/help"
                aria-label="Help"
                sx={{
                  color: "inherit",
                  border: "1px solid rgba(255,255,255,0.6)",
                  width: 36,
                  height: 36,
                }}
              >
                <Typography sx={{ fontWeight: "bold" }}>?</Typography>
              </IconButton>
            </Tooltip>
          </Box>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: { width: DRAWER_WIDTH, boxSizing: "border-box" },
        }}
      >
        <Toolbar />
        <List>
          {NAV_ITEMS.map((item) => (
            <ListItemButton
              key={item.path}
              component={Link}
              to={item.path}
              selected={location.pathname === item.path}
            >
              <ListItemText primary={item.label} />
            </ListItemButton>
          ))}
        </List>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        <Outlet />
      </Box>
      <Snackbar
        open={refreshPromptOpen}
        autoHideDuration={8000}
        onClose={() => setRefreshPromptOpen(false)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        message="Saved. Update every other open page with this change?"
        action={
          <>
            <Button color="inherit" size="small" onClick={handleRefreshAll}>
              Update All
            </Button>
            <Button color="inherit" size="small" onClick={() => setRefreshPromptOpen(false)}>
              Not now
            </Button>
          </>
        }
      />
    </Box>
  );
}
