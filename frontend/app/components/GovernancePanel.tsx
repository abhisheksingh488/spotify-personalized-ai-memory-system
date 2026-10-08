"use client";

export default function GovernancePanel() {
  return (
    <section className="governance-panel">
      <div className="governance-header">
        <div>
          <h2>Schema & Policy</h2>
          <p>
            Memory governance, schema rules and persistence policy.
          </p>
        </div>
      </div>

      <div className="governance-grid">
        <div className="governance-card">
          <h3>Memory Schema</h3>

          <div className="governance-row">
            <span>Memory ID</span>
            <strong>UUID</strong>
          </div>

          <div className="governance-row">
            <span>Subject ID</span>
            <strong>Required</strong>
          </div>

          <div className="governance-row">
            <span>Memory Type</span>
            <strong>Typed</strong>
          </div>

          <div className="governance-row">
            <span>Fact Text</span>
            <strong>Required</strong>
          </div>

          <div className="governance-row">
            <span>Confidence</span>
            <strong>0.0 – 1.0</strong>
          </div>

          <div className="governance-row">
            <span>Provenance</span>
            <strong>Required</strong>
          </div>

          <div className="governance-row">
            <span>Temporal Scope</span>
            <strong>Supported</strong>
          </div>
        </div>

        <div className="governance-card">
          <h3>Persistence Policy</h3>

          <div className="policy-item allowed">
            <span>✓</span>
            <div>
              <strong>Standard</strong>
              <p>Eligible for durable memory.</p>
            </div>
          </div>

          <div className="policy-item blocked">
            <span>×</span>
            <div>
              <strong>Blocked</strong>
              <p>Must not be persisted.</p>
            </div>
          </div>

          <div className="policy-item blocked">
            <span>×</span>
            <div>
              <strong>Sensitive</strong>
              <p>Excluded from durable persistence.</p>
            </div>
          </div>

          <div className="policy-item allowed">
            <span>✓</span>
            <div>
              <strong>User Correction</strong>
              <p>Creates a correction and supersedes old memory.</p>
            </div>
          </div>
        </div>

        <div className="governance-card">
          <h3>Retrieval Rules</h3>

          <div className="governance-row">
            <span>Subject Isolation</span>
            <strong>Required</strong>
          </div>

          <div className="governance-row">
            <span>Policy Filter</span>
            <strong>Enabled</strong>
          </div>

          <div className="governance-row">
            <span>Active Memory</span>
            <strong>Only</strong>
          </div>

          <div className="governance-row">
            <span>Hybrid Retrieval</span>
            <strong>Enabled</strong>
          </div>

          <div className="governance-row">
            <span>Provenance</span>
            <strong>Included</strong>
          </div>
        </div>
      </div>
    </section>
  );
}