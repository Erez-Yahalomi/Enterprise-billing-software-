import { Box, Button, Card, CardActionArea, CardContent, Stack, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";

import { startDemoWorkspace, startMyWorkspace } from "../api/client";

export default function FirstLogin() {
  const navigate = useNavigate();

  const chooseDemo = () => {
    startDemoWorkspace();
    navigate("/");
  };

  const chooseMyWorkspace = () => {
    startMyWorkspace();
    navigate("/");
  };

  return (
    <Box sx={{ maxWidth: 720, mx: "auto", mt: 10, textAlign: "center" }}>
      <Typography variant="h4" gutterBottom>
        Welcome to the Corporate Billing Platform
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        How would you like to start?
      </Typography>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={3} justifyContent="center">
        <Card sx={{ flex: 1 }}>
          <CardActionArea onClick={chooseDemo} sx={{ p: 2, height: "100%" }}>
            <CardContent>
              <Typography variant="h6">Explore Demo</Typography>
              <Typography variant="body2" color="text.secondary">
                Use preloaded customers, invoices, subscriptions, usage, payments, and analytics.
              </Typography>
            </CardContent>
          </CardActionArea>
        </Card>
        <Card sx={{ flex: 1 }}>
          <CardActionArea onClick={chooseMyWorkspace} sx={{ p: 2, height: "100%" }}>
            <CardContent>
              <Typography variant="h6">Start My Workspace</Typography>
              <Typography variant="body2" color="text.secondary">
                Create real customers and use the system with your own data.
              </Typography>
            </CardContent>
          </CardActionArea>
        </Card>
      </Stack>
      <Button sx={{ mt: 4 }} onClick={chooseDemo}>
        Skip for now
      </Button>
    </Box>
  );
}
