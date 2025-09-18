import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import { RefreshProvider } from './contexts/RefreshContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Networks from './pages/Networks'
import NetworkDetail from './pages/NetworkDetail'
import NetworkGraph from './pages/NetworkGraph'

function App() {
    return (
        <ThemeProvider>
            <RefreshProvider>
                <Router>
                    <Layout>
                        <Routes>
                            <Route path="/" element={<Dashboard />} />
                            <Route path="/networks" element={<Networks />} />
                            <Route path="/networks/:networkId" element={<NetworkDetail />} />
                            <Route path="/graph" element={<NetworkGraph />} />
                        </Routes>
                    </Layout>
                </Router>
            </RefreshProvider>
        </ThemeProvider>
    )
}

export default App
