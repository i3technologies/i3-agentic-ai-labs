/**
 * tracing.ts
 * OpenTelemetry Node SDK initialisation — STEP-P1-14.
 * Must be imported BEFORE any other module so instrumentation patches apply.
 * Exports `tracer` for manual span creation in planner.ts and base-scan.ts.
 */

import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { trace } from '@opentelemetry/api';

const sdk = new NodeSDK({
  traceExporter: new OTLPTraceExporter({
    url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT
      ?? 'http://otel-collector.i3-monitoring.svc.cluster.local:4317',
  }),
  instrumentations: [getNodeAutoInstrumentations()],
});

sdk.start();

// Ensure clean shutdown on process termination
process.on('SIGTERM', () => { sdk.shutdown().finally(() => process.exit(0)); });

export const tracer = trace.getTracer('onboarding-agent');
