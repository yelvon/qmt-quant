import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import DashboardPage from "./pages/DashboardPage";
import DataPage from "./pages/DataPage";
import DataBrowsePage from "./pages/DataBrowsePage";
import ResearchPage from "./pages/ResearchPage";
import ValidationPage from "./pages/ValidationPage";
import ScreeningPage from "./pages/ScreeningPage";
import LivePage from "./pages/LivePage";
import SettingsPage from "./pages/SettingsPage";
import JobsPage from "./pages/JobsPage";
import IcPage from "./pages/IcPage";
import HelpPage from "./pages/HelpPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/data" element={<DataPage />} />
        <Route path="/data/browse" element={<DataBrowsePage />} />
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/validation" element={<ValidationPage />} />
        <Route path="/screening" element={<ScreeningPage />} />
        <Route path="/live" element={<LivePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/ic" element={<IcPage />} />
        <Route path="/help" element={<HelpPage />} />
      </Route>
    </Routes>
  );
}
