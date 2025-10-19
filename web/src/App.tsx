import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import { RefreshProvider } from './contexts/RefreshContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import NetworkDetail from './pages/NetworkDetail'
import NetworkGraph from './pages/NetworkGraph'
import NotificationClusterPage from './pages/NotificationCluster'
import EventsPage from './pages/Events'
import ClusterPage from './pages/Cluster'

function App() {
    return (
        <ThemeProvider>
            <RefreshProvider>
                <Router>
                    <Layout>
                        <Routes>
                            <Route path="/" element={<Dashboard />} />
                            <Route path="/networks/:networkId" element={<NetworkDetail />} />
                            <Route path="/graph" element={<NetworkGraph />} />
                            <Route path="/notification-cluster" element={<NotificationClusterPage />} />
                            <Route path="/cluster" element={<ClusterPage />} />
                            <Route path="/events" element={<EventsPage />} />
                        </Routes>
                    </Layout>
                </Router>
            </RefreshProvider>
        </ThemeProvider>
    )
}

export default App
