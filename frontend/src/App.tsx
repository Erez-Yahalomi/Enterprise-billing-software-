import { Navigate, Route, Routes } from "react-router-dom";

import { getWorkspace } from "./api/client";
import AppShell from "./layout/AppShell";
import AIAssistant from "./pages/AIAssistant";
import Analytics from "./pages/Analytics";
import Customers from "./pages/Customers";
import CustomerDetail from "./pages/CustomerDetail";
import Dashboard from "./pages/Dashboard";
import DemoData from "./pages/DemoData";
import FirstLogin from "./pages/FirstLogin";
import Help from "./pages/Help";
import InvoiceDetail from "./pages/InvoiceDetail";
import Invoices from "./pages/Invoices";
import Payments from "./pages/Payments";
import Products from "./pages/Products";
import SubscriptionDetail from "./pages/SubscriptionDetail";
import Subscriptions from "./pages/Subscriptions";
import Usage from "./pages/Usage";

function RequireWorkspace({ children }: { children: JSX.Element }) {
  if (!getWorkspace()) return <Navigate to="/welcome" replace />;
  return children;
}

function App() {
  return (
    <Routes>
      <Route path="/welcome" element={<FirstLogin />} />
      <Route
        element={
          <RequireWorkspace>
            <AppShell />
          </RequireWorkspace>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/customers" element={<Customers />} />
        <Route path="/customers/:customerId" element={<CustomerDetail />} />
        <Route path="/products" element={<Products />} />
        <Route path="/subscriptions" element={<Subscriptions />} />
        <Route path="/subscriptions/:subscriptionId" element={<SubscriptionDetail />} />
        <Route path="/usage" element={<Usage />} />
        <Route path="/invoices" element={<Invoices />} />
        <Route path="/invoices/:invoiceId" element={<InvoiceDetail />} />
        <Route path="/payments" element={<Payments />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/ai" element={<AIAssistant />} />
        <Route path="/demo-data" element={<DemoData />} />
        <Route path="/help" element={<Help />} />
      </Route>
    </Routes>
  );
}

export default App;
