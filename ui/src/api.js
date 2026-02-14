export async function searchJobs(query, topK = 20) {
  const response = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`);
  }
  return response.json();
}

export async function refineJobs(query, context, topK = 20) {
  const response = await fetch("/api/refine", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, context, top_k: topK }),
  });
  if (!response.ok) {
    throw new Error(`Refine failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchTokenMetrics(recentLimit = 10) {
  const response = await fetch(
    `/api/metrics/tokens?recent_limit=${encodeURIComponent(recentLimit)}`,
  );
  if (!response.ok) {
    throw new Error(`Metrics fetch failed: ${response.status}`);
  }
  return response.json();
}

export async function sendFeedback(payload) {
  const body = JSON.stringify(payload);
  if (navigator.sendBeacon) {
    const blob = new Blob([body], { type: "application/json" });
    navigator.sendBeacon("/api/feedback", blob);
    return;
  }
  await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  });
}
