import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Networks from './pages/Networks'
import NetworkDetail from './pages/NetworkDetail'

function App() {
    return (
        <ThemeProvider>
            <Router>
                <Layout>
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/networks" element={<Networks />} />
                        <Route path="/networks/:networkId" element={<NetworkDetail />} />
                    </Routes>
                </Layout>
            </Router>
        </ThemeProvider>
    )
}

export default App
