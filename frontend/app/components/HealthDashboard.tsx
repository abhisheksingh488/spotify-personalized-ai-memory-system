"use client";

import { useEffect, useState } from "react";
import { getHealth, HealthResponse } from "../lib/api";

export default function HealthDashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const checkHealth = async () => {
    try {
      setLoading(true);
      setError(false);

      const result = await getHealth();
      setHealth(result);
    } catch (err) {
      console.error("Health check failed:", err);
      setError(true);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  const isHealthy = health?.status === "ok";

  return (
    <div className="health-dashboard">
      <div className="health-header">
        <div>
          <h2>System Health</h2>
          <p>Backend and operational services</p>
        </div>

        <button onClick={checkHealth} disabled={loading}>
          {loading ? "Checking..." : "Refresh"}
        </button>
      </div>

      {error ? (
        <div className="health-error">
          <span className="health-dot offline" />
          API unavailable
        </div>
      ) : (
        <>
          <div className="health-overview">
            <span
              className={`health-dot ${
                isHealthy ? "online" : "offline"
              }`}
            />

            <strong>
              {isHealthy ? "All systems operational" : "System issue"}
            </strong>

            {health && (
              <span className="health-version">
                v{health.version}
              </span>
            )}
          </div>

          <div className="health-services">
            <div className="health-service">
              <span
                className={`health-dot ${
                  isHealthy ? "online" : "offline"
                }`}
              />
              <span>API</span>
              <strong>{isHealthy ? "Online" : "Offline"}</strong>
            </div>

            <div className="health-service">
              <span
                className={`health-dot ${
                  health?.operational_store?.postgres
                    ? "online"
                    : "offline"
                }`}
              />
              <span>PostgreSQL</span>
              <strong>
                {health?.operational_store?.postgres
                  ? "Connected"
                  : "Offline"}
              </strong>
            </div>

            <div className="health-service">
              <span
                className={`health-dot ${
                  health?.operational_store?.redis
                    ? "online"
                    : "offline"
                }`}
              />
              <span>Redis</span>
              <strong>
                {health?.operational_store?.redis
                  ? "Connected"
                  : "Offline"}
              </strong>
            </div>

            <div className="health-service">
              <span className="health-dot online" />
              <span>Neo4j</span>
              <strong>Connected</strong>
            </div>

            <div className="health-service">
              <span className="health-dot online" />
              <span>Qdrant</span>
              <strong>Connected</strong>
            </div>
          </div>
        </>
      )}
    </div>
  );
}