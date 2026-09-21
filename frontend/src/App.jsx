import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./context/AuthContext";
import Admin from "./pages/Admin";
import ComingSoon from "./pages/ComingSoon";
import Customer from "./pages/Customer";
import Customer360 from "./pages/Customer360";
import DailyAction from "./pages/DailyAction";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Merchant from "./pages/Merchant";
import MonthlyReport from "./pages/MonthlyReport";
import More from "./pages/More";
import Pipeline from "./pages/Pipeline";
import Realisasi from "./pages/Realisasi";
import RmftDetail from "./pages/RmftDetail";
import RmftList from "./pages/RmftList";
import RmftPerformance from "./pages/RmftPerformance";
import Target from "./pages/Target";
import Upload from "./pages/Upload";
import WaReport from "./pages/WaReport";

function Protected({ children, adminOnly }) {
  const { profile, isAdmin } = useAuth();
  if (!profile) return <Navigate to="/login" replace />;
  if (adminOnly && !isAdmin) {
    return <ComingSoon title="Akses Terbatas" phase="Admin/SBOH" description="Menu ini hanya dapat diakses oleh Admin/SBOH." />;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/" element={<Home />} />
        <Route path="/funding" element={<RmftList />} />
        <Route path="/funding/:pn" element={<RmftDetail />} />
        <Route path="/merchant" element={<Merchant />} />
        <Route path="/rmft-performance" element={<RmftPerformance />} />
        <Route path="/upload" element={<Protected adminOnly><Upload /></Protected>} />
        <Route path="/more" element={<More />} />

        <Route path="/daily-action" element={<DailyAction />} />
        <Route path="/pipeline" element={<Pipeline />} />
        <Route path="/realisasi" element={<Realisasi />} />
        <Route path="/customer" element={<Customer />} />
        <Route path="/customer/360" element={<Customer360 />} />
        <Route path="/monthly-report" element={<MonthlyReport />} />
        <Route path="/wa-report" element={<WaReport />} />
        <Route path="/target" element={<Target />} />
        <Route path="/admin" element={<Protected adminOnly><Admin /></Protected>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
