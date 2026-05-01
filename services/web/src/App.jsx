import { useEffect, useState } from "react";
import { compareLogs, fetchLogDetail, fetchLogs, fetchSummary, login } from "./api";
import { buildComparisonTexts, buildDetailView, buildLogRows, buildMetricCards } from "./presenters";

const defaultCredentials = {
  email: "admin@example.com",
  password: "changeme",
};

function MetricCard({ label, value }) {
  return (
    <section className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </section>
  );
}

export default function App() {
  const [credentials, setCredentials] = useState(defaultCredentials);
  const [token, setToken] = useState("");
  const [summary, setSummary] = useState(null);
  const [logs, setLogs] = useState([]);
  const [selectedLog, setSelectedLog] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const metricCards = buildMetricCards(summary);
  const logRows = buildLogRows(logs);
  const detailView = buildDetailView(selectedLog);
  const comparisonTexts = buildComparisonTexts(comparison);

  async function loadDashboard(activeToken, searchValue = "") {
    const summaryPayload = await fetchSummary(activeToken);
    const query = searchValue ? new URLSearchParams({ search: searchValue }).toString() : "";
    const logsPayload = await fetchLogs(activeToken, query);
    setSummary(summaryPayload);
    setLogs(logsPayload.items);
  }

  async function handleLogin(event) {
    event.preventDefault();
    try {
      setError("");
      const response = await login(credentials.email, credentials.password);
      setToken(response.access_token);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSelectLog(requestId) {
    try {
      setSelectedLog(await fetchLogDetail(token, requestId));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCompare() {
    if (logs.length < 2) {
      return;
    }
    try {
      const response = await compareLogs(token, logs[0].request_id, logs[1].request_id);
      setComparison(response);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (!token) {
      return;
    }
    loadDashboard(token, search).catch((err) => setError(err.message));
  }, [token]);

  if (!token) {
    return (
      <main className="page-shell">
        <section className="auth-panel">
          <h1>AI Monitoring</h1>
          <p>Sign in to inspect AI requests, latency, cost, and failures.</p>
          <form onSubmit={handleLogin}>
            <label>
              Email
              <input
                value={credentials.email}
                onChange={(event) => setCredentials({ ...credentials, email: event.target.value })}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={credentials.password}
                onChange={(event) => setCredentials({ ...credentials, password: event.target.value })}
              />
            </label>
            <button type="submit">Sign In</button>
          </form>
          {error ? <p className="error-message">{error}</p> : null}
        </section>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Observability Dashboard</p>
          <h1>Production visibility for every LLM request</h1>
        </div>
        <div className="hero-actions">
          <input
            placeholder="Search prompts or outputs"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <button type="button" onClick={() => loadDashboard(token, search)}>
            Refresh
          </button>
          <button type="button" onClick={handleCompare}>
            Compare Latest Two
          </button>
        </div>
      </header>

      {metricCards.length ? (
        <section className="metric-grid">
          {metricCards.map((card) => (
            <MetricCard key={card.label} label={card.label} value={card.value} />
          ))}
        </section>
      ) : null}

      <section className="content-grid">
        <section className="panel">
          <h2>Logs Explorer</h2>
          <div className="log-list">
            {logRows.map((log) => (
              <button key={log.requestId} className="log-row" type="button" onClick={() => handleSelectLog(log.requestId)}>
                <strong>{log.requestId}</strong>
                <span>{log.model}</span>
                <span>{log.status}</span>
                <span>{log.preview}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>Request Detail</h2>
          {detailView ? (
            <div className="detail-stack">
              <p><strong>Feature:</strong> {detailView.feature}</p>
              <p><strong>Latency:</strong> {detailView.latency}</p>
              <p><strong>Cost:</strong> {detailView.cost}</p>
              <p><strong>System Prompt:</strong> {detailView.systemPrompt}</p>
              <pre>{detailView.inputMessages}</pre>
              <pre>{detailView.outputMessages}</pre>
            </div>
          ) : (
            <p>Select a request to inspect its full prompt and response payload.</p>
          )}
        </section>
      </section>

      {comparisonTexts.length ? (
        <section className="panel comparison-panel">
          <h2>Compare Outputs</h2>
          <div className="comparison-grid">
            {comparisonTexts.map((text, index) => (
              <pre key={index}>{text}</pre>
            ))}
          </div>
        </section>
      ) : null}

      {error ? <p className="error-message">{error}</p> : null}
    </main>
  );
}
