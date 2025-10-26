import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [topK, setTopK] = useState(5)

  // Advanced search features
  const [searchMode, setSearchMode] = useState('simple') // simple, advanced, synthesis, structured
  const [queryType, setQueryType] = useState('simple') // simple, multi_dimensional, scenario, trend_stack
  const [dimensions, setDimensions] = useState([])
  const [dimensionInput, setDimensionInput] = useState('')
  const [scenario, setScenario] = useState('')
  const [trends, setTrends] = useState([])
  const [trendInput, setTrendInput] = useState('')
  const [enableExpansion, setEnableExpansion] = useState(false)
  const [categories, setCategories] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('')

  // Use environment variables for API configuration (from .env file)
  // In Vite, environment variables must be prefixed with VITE_
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const API_KEY = import.meta.env.VITE_API_KEY || ''

  // Check feature flags from environment
  const ENABLE_ADVANCED = import.meta.env.VITE_ENABLE_ADVANCED_SEARCH !== 'false'
  const ENABLE_CATEGORIES = import.meta.env.VITE_ENABLE_CATEGORIES !== 'false'
  const ENABLE_SYNTHESIS = import.meta.env.VITE_ENABLE_SYNTHESIS !== 'false'

  // Warn if API key is not configured
  if (!import.meta.env.VITE_API_KEY) {
    console.warn('⚠️ VITE_API_KEY not configured. Please create frontend/.env file. See .env.example for template.')
  }

  // Load categories on mount
  useEffect(() => {
    if (ENABLE_CATEGORIES) {
      fetchCategories()
    }
  }, [])

  const fetchCategories = async () => {
    try {
      const response = await fetch(`${API_URL}/categories`)
      if (response.ok) {
        const data = await response.json()
        setCategories(data.categories || [])
      }
    } catch (err) {
      console.error('Failed to load categories:', err)
    }
  }

  const addDimension = () => {
    if (dimensionInput.trim() && !dimensions.includes(dimensionInput.trim())) {
      setDimensions([...dimensions, dimensionInput.trim()])
      setDimensionInput('')
    }
  }

  const removeDimension = (index) => {
    setDimensions(dimensions.filter((_, i) => i !== index))
  }

  const addTrend = () => {
    if (trendInput.trim() && !trends.includes(trendInput.trim())) {
      setTrends([...trends, trendInput.trim()])
      setTrendInput('')
    }
  }

  const removeTrend = (index) => {
    setTrends(trends.filter((_, i) => i !== index))
  }

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
      let endpoint = '/search'
      let body = {
        query: query.trim(),
        top_k: topK
      }

      // Determine endpoint and body based on search mode
      if (searchMode === 'synthesis') {
        endpoint = '/search/synthesized'
      } else if (searchMode === 'structured') {
        endpoint = '/search/structured'
      } else if (searchMode === 'advanced') {
        endpoint = '/search/advanced'
        body = {
          query: query.trim(),
          query_type: queryType,
          top_k: topK,
          enable_expansion: enableExpansion
        }

        // Add type-specific parameters
        if (queryType === 'multi_dimensional' && dimensions.length > 0) {
          body.dimensions = dimensions
        } else if (queryType === 'scenario' && scenario.trim()) {
          body.scenario = scenario.trim()
        } else if (queryType === 'trend_stack' && trends.length > 0) {
          body.trends = trends
        }
      }

      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${API_KEY}`
        },
        body: JSON.stringify(body)
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
        <h1>🔍 Trend Intelligence Platform</h1>
        <p className="subtitle">AI-powered creative strategy insights across 51 trend reports</p>
      </header>

      <main className="main">
        {/* Search Mode Selector */}
        <div className="mode-selector">
          <button
            className={`mode-button ${searchMode === 'simple' ? 'active' : ''}`}
            onClick={() => setSearchMode('simple')}
          >
            Simple Search
          </button>
          {ENABLE_ADVANCED && (
            <button
              className={`mode-button ${searchMode === 'advanced' ? 'active' : ''}`}
              onClick={() => setSearchMode('advanced')}
            >
              Advanced Search
            </button>
          )}
          {ENABLE_SYNTHESIS && (
            <button
              className={`mode-button ${searchMode === 'synthesis' ? 'active' : ''}`}
              onClick={() => setSearchMode('synthesis')}
            >
              Synthesis
            </button>
          )}
          {ENABLE_SYNTHESIS && (
            <button
              className={`mode-button ${searchMode === 'structured' ? 'active' : ''}`}
              onClick={() => setSearchMode('structured')}
            >
              Structured Report
            </button>
          )}
        </div>

        <form onSubmit={handleSearch} className="search-form">
          {/* Main Query Input */}
          <div className="search-input-group">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={
                searchMode === 'synthesis'
                  ? "What trends are you investigating?"
                  : searchMode === 'structured'
                  ? "Describe your strategic question..."
                  : "Search trends (e.g., AI in advertising, social media marketing...)"
              }
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

          {/* Advanced Search Options */}
          {searchMode === 'advanced' && (
            <div className="advanced-options">
              <div className="query-type-selector">
                <label>Query Type:</label>
                <select
                  value={queryType}
                  onChange={(e) => setQueryType(e.target.value)}
                  className="query-type-select"
                  disabled={loading}
                >
                  <option value="simple">Simple</option>
                  <option value="multi_dimensional">Multi-Dimensional</option>
                  <option value="scenario">Scenario-Based</option>
                  <option value="trend_stack">Trend Stacking</option>
                </select>
              </div>

              {queryType === 'simple' && (
                <div className="expansion-toggle">
                  <label>
                    <input
                      type="checkbox"
                      checked={enableExpansion}
                      onChange={(e) => setEnableExpansion(e.target.checked)}
                      disabled={loading}
                    />
                    Enable query expansion for broader results
                  </label>
                </div>
              )}

              {queryType === 'multi_dimensional' && (
                <div className="dimensions-input">
                  <label>Additional Dimensions (e.g., "sustainability", "Gen Z"):</label>
                  <div className="chip-input-group">
                    <input
                      type="text"
                      value={dimensionInput}
                      onChange={(e) => setDimensionInput(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addDimension())}
                      placeholder="Add dimension..."
                      className="chip-input"
                      disabled={loading}
                    />
                    <button
                      type="button"
                      onClick={addDimension}
                      className="chip-add-button"
                      disabled={loading}
                    >
                      Add
                    </button>
                  </div>
                  <div className="chips-container">
                    {dimensions.map((dim, index) => (
                      <span key={index} className="chip">
                        {dim}
                        <button
                          type="button"
                          onClick={() => removeDimension(index)}
                          className="chip-remove"
                          disabled={loading}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {queryType === 'scenario' && (
                <div className="scenario-input">
                  <label>Scenario Description:</label>
                  <textarea
                    value={scenario}
                    onChange={(e) => setScenario(e.target.value)}
                    placeholder="Describe the scenario (e.g., 'What if luxury brands enter the metaverse?')"
                    className="scenario-textarea"
                    rows="3"
                    disabled={loading}
                  />
                </div>
              )}

              {queryType === 'trend_stack' && (
                <div className="trends-input">
                  <label>Trends to Stack:</label>
                  <div className="chip-input-group">
                    <input
                      type="text"
                      value={trendInput}
                      onChange={(e) => setTrendInput(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTrend())}
                      placeholder="Add trend..."
                      className="chip-input"
                      disabled={loading}
                    />
                    <button
                      type="button"
                      onClick={addTrend}
                      className="chip-add-button"
                      disabled={loading}
                    >
                      Add
                    </button>
                  </div>
                  <div className="chips-container">
                    {trends.map((trend, index) => (
                      <span key={index} className="chip">
                        {trend}
                        <button
                          type="button"
                          onClick={() => removeTrend(index)}
                          className="chip-remove"
                          disabled={loading}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <button type="submit" className="search-button" disabled={loading}>
            {loading ? 'Searching...' : searchMode === 'synthesis' ? 'Synthesize' : searchMode === 'structured' ? 'Generate Report' : 'Search'}
          </button>
        </form>

        {error && (
          <div className="error-message">
            ❌ {error}
          </div>
        )}

        {/* Results Display - Different formats based on search mode */}
        {results && Object.keys(results).length > 0 && (
          <div className="results-container">
            {/* Synthesis Results */}
            {searchMode === 'synthesis' && results.summary && (
              <div className="synthesis-results">
                <div className="synthesis-header">
                  <h2>Cross-Report Synthesis</h2>
                  <div className="meta-info">
                    <span>📊 {results.meta_analysis?.unique_reports || 0} reports analyzed</span>
                    <span>✨ {results.meta_analysis?.meta_trends_count || 0} meta-trends identified</span>
                    <span>🎯 {results.meta_analysis?.coverage_quality || 'N/A'} coverage</span>
                  </div>
                </div>

                <div className="synthesis-summary">
                  <h3>Executive Summary</h3>
                  <p>{results.summary}</p>
                </div>

                {results.meta_trends && results.meta_trends.length > 0 && (
                  <div className="meta-trends-section">
                    <h3>Meta-Trends Identified</h3>
                    {results.meta_trends.map((trend, index) => (
                      <div key={index} className="meta-trend-card">
                        <div className="trend-header">
                          <h4>{trend.theme}</h4>
                          <span className={`confidence-badge ${trend.confidence}`}>
                            {trend.confidence} confidence
                          </span>
                        </div>
                        <p className="trend-description">{trend.description}</p>
                        <div className="trend-sources">
                          <strong>Sources ({trend.source_count}):</strong>
                          <div className="source-tags">
                            {trend.sources.slice(0, 5).map((source, i) => (
                              <span key={i} className="source-tag">{source}</span>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {results.consensus_themes && results.consensus_themes.length > 0 && (
                  <div className="consensus-section">
                    <h3>Consensus Themes</h3>
                    <ul>
                      {results.consensus_themes.map((theme, index) => (
                        <li key={index}>{theme}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Structured Response Results */}
            {searchMode === 'structured' && results.relevant_trends && (
              <div className="structured-results">
                <div className="structured-header">
                  <h2>Strategic Intelligence Report</h2>
                  <div className="report-meta">
                    <span>📚 {results.sources_analyzed} sources</span>
                    <span className={`confidence-badge ${results.confidence_level}`}>
                      {results.confidence_level} confidence
                    </span>
                  </div>
                </div>

                <div className="relevant-trends-section">
                  <h3>Key Trends</h3>
                  <ul className="trends-list">
                    {results.relevant_trends.map((trend, index) => (
                      <li key={index} className="trend-item">{trend}</li>
                    ))}
                  </ul>
                </div>

                <div className="context-section">
                  <h3>Strategic Context</h3>
                  <p>{results.context}</p>
                </div>

                {results.data_points && results.data_points.length > 0 && (
                  <div className="data-points-section">
                    <h3>Key Data Points</h3>
                    <div className="data-points-grid">
                      {results.data_points.map((dp, index) => (
                        <div key={index} className="data-point-card">
                          <div className="statistic">{dp.statistic}</div>
                          <div className="source-info">
                            <span className="source">📄 {dp.source}</span>
                            {dp.context && <span className="context">{dp.context}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {results.applications && results.applications.length > 0 && (
                  <div className="applications-section">
                    <h3>Practical Applications</h3>
                    <ul className="applications-list">
                      {results.applications.map((app, index) => (
                        <li key={index}>{app}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {results.connections && results.connections.length > 0 && (
                  <div className="connections-section">
                    <h3>Opportunity Intersections</h3>
                    <ul className="connections-list">
                      {results.connections.map((conn, index) => (
                        <li key={index}>{conn}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {results.next_steps && results.next_steps.length > 0 && (
                  <div className="next-steps-section">
                    <h3>Recommended Next Steps</h3>
                    <ol className="next-steps-list">
                      {results.next_steps.map((step, index) => (
                        <li key={index}>{step}</li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            )}

            {/* Simple or Advanced Results */}
            {(searchMode === 'simple' || searchMode === 'advanced') && results.results && (
              <div className="standard-results">
                <div className="results-header">
                  <h2>
                    {results.query_type && results.query_type !== 'simple' && (
                      <span className="query-type-badge">{results.query_type.replace('_', ' ')}</span>
                    )}
                    Found {results.results.length} result{results.results.length !== 1 ? 's' : ''}
                  </h2>
                  {results.metadata && (
                    <div className="metadata-info">
                      {results.metadata.total_dimensions && (
                        <span>🔍 {results.metadata.total_dimensions} dimensions</span>
                      )}
                      {results.metadata.total_trends && (
                        <span>📊 {results.metadata.total_trends} trends</span>
                      )}
                      {results.metadata.total_variants && (
                        <span>🔄 {results.metadata.total_variants} query variants</span>
                      )}
                    </div>
                  )}
                </div>
                <div className="results-list">
                  {results.results.map((result, index) => (
                    <div key={index} className="result-card">
                      <div className="result-header">
                        <div className="result-meta">
                          <span className="result-source" title={result.source}>
                            📄 {result.source}
                          </span>
                          <span className="result-page">Page {result.page}</span>
                          <span className="result-score" title="Relevance Score">
                            🎯 {((result.relevance_score || result.multi_dim_score || result.synergy_score || 0) * 100).toFixed(1)}%
                          </span>
                        </div>
                        {result.dimensions_matched && (
                          <div className="dimensions-matched">
                            <strong>Matched:</strong> {result.dimensions_matched.join(', ')}
                          </div>
                        )}
                        {result.trends_found && (
                          <div className="trends-found">
                            <strong>Trends:</strong> {result.trends_found.join(', ')}
                          </div>
                        )}
                      </div>
                      <div className="result-content">
                        {result.content}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {!loading && !error && (!results || Object.keys(results).length === 0) && query && (
          <div className="no-results">
            No results found for "{query}"
          </div>
        )}

        {!query && !loading && (!results || Object.keys(results).length === 0) && (
          <div className="welcome-message">
            <h2>Welcome to Trend Intelligence Platform</h2>
            <p className="welcome-intro">
              AI-powered creative strategy insights across 6,109 indexed documents from 51 trend reports
            </p>
            <div className="features-grid">
              <div className="feature-card">
                <h3>🔍 Simple Search</h3>
                <p>Fast semantic search across all reports</p>
              </div>
              {ENABLE_ADVANCED && (
                <div className="feature-card">
                  <h3>🎯 Advanced Search</h3>
                  <p>Multi-dimensional, scenario-based, and trend stacking queries</p>
                </div>
              )}
              {ENABLE_SYNTHESIS && (
                <div className="feature-card">
                  <h3>📊 Synthesis</h3>
                  <p>Cross-report meta-trends and consensus analysis</p>
                </div>
              )}
              {ENABLE_SYNTHESIS && (
                <div className="feature-card">
                  <h3>📝 Structured Reports</h3>
                  <p>Professional strategic intelligence reports</p>
                </div>
              )}
            </div>
            <div className="categories-preview">
              <h3>Trend Categories</h3>
              <ul>
                <li>Consumer & Culture</li>
                <li>Technology & Innovation</li>
                <li>Marketing & Advertising</li>
                <li>Business & Industry</li>
                <li>Customer Experience</li>
              </ul>
            </div>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Powered by Claude 3.5 Sonnet • ChromaDB • FastEmbed • React</p>
      </footer>
    </div>
  )
}

export default App
