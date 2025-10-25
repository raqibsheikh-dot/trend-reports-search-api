import { useState } from 'react'
import './App.css'

function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [topK, setTopK] = useState(5)

  const API_URL = 'http://localhost:8000'
  const API_KEY = '10dafba9ff7c619de2029ed1044cafec4f282e812c51ef8627627480aeb0d89d'

  const handleSearch = async (e) => {
    e.preventDefault()

    if (!query.trim()) {
      setError('Please enter a search query')
      return
    }

    setLoading(true)
    setError(null)
    setResults([])

    try {
      const response = await fetch(`${API_URL}/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${API_KEY}`
        },
        body: JSON.stringify({
          query: query.trim(),
          top_k: topK
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Search failed')
      }

      const data = await response.json()
      setResults(data)
    } catch (err) {
      setError(err.message)
      console.error('Search error:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>🔍 Trend Reports Search</h1>
        <p className="subtitle">AI-powered semantic search across 51 trend reports</p>
      </header>

      <main className="main">
        <form onSubmit={handleSearch} className="search-form">
          <div className="search-input-group">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search trends (e.g., AI in advertising, social media marketing...)"
              className="search-input"
              disabled={loading}
            />
            <div className="top-k-control">
              <label htmlFor="topK">Results:</label>
              <input
                id="topK"
                type="number"
                value={topK}
                onChange={(e) => setTopK(Math.min(20, Math.max(1, parseInt(e.target.value) || 5)))}
                min="1"
                max="20"
                className="top-k-input"
                disabled={loading}
              />
            </div>
          </div>
          <button type="submit" className="search-button" disabled={loading}>
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>

        {error && (
          <div className="error-message">
            ❌ {error}
          </div>
        )}

        {results.length > 0 && (
          <div className="results-container">
            <div className="results-header">
              <h2>Found {results.length} result{results.length !== 1 ? 's' : ''}</h2>
            </div>
            <div className="results-list">
              {results.map((result, index) => (
                <div key={index} className="result-card">
                  <div className="result-header">
                    <div className="result-meta">
                      <span className="result-source" title={result.source}>
                        📄 {result.source}
                      </span>
                      <span className="result-page">Page {result.page}</span>
                      <span className="result-score" title="Relevance Score">
                        🎯 {(result.relevance_score * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="result-content">
                    {result.content}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {!loading && !error && results.length === 0 && query && (
          <div className="no-results">
            No results found for "{query}"
          </div>
        )}

        {!query && !loading && results.length === 0 && (
          <div className="welcome-message">
            <h2>Welcome to Trend Reports Search</h2>
            <p>Search across 6,109 indexed documents from 51 trend reports covering:</p>
            <ul>
              <li>AI & Marketing Automation</li>
              <li>Social Media Trends</li>
              <li>Customer Experience</li>
              <li>E-commerce & Retail</li>
              <li>Digital Advertising</li>
              <li>Consumer Behavior</li>
            </ul>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Powered by FastAPI • ChromaDB • FastEmbed (BAAI/bge-small-en-v1.5)</p>
      </footer>
    </div>
  )
}

export default App
